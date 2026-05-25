"""
step1_ocr/extractor.py
----------------------
Extração de dados de notas fiscais a partir de PDF ou imagem.

Rotas:
  - PDF nativo  → pdfplumber extrai texto diretamente
  - PDF/imagem escaneada → OpenCV pré-processa + pytesseract faz OCR

Saída: dataclass NotaFiscal com confidence_score por campo.
"""

import re
import pdfplumber
import pytesseract
import cv2
import numpy as np
import platform
from pdf2image import convert_from_path
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# Instalação TesseracT
# ────────────────────────────────────────────

import os
import subprocess
import shutil

def verificar_tesseract():
    caminho_padrao = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    tesseract_no_path = shutil.which("tesseract")

    # Verifica se realmente existe no disco, não só no PATH
    if tesseract_no_path and os.path.isfile(tesseract_no_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_no_path
        print("✔ Tesseract já instalado.")
        return

    if os.path.isfile(caminho_padrao):
        pytesseract.pytesseract.tesseract_cmd = caminho_padrao
        print("✔ Tesseract já instalado.")
        return

    print("⚠ Tesseract não encontrado. Instalando...")
    url = "https://github.com/UB-Mannheim/tesseract/releases/download/v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
    instalador = os.path.join(os.environ["TEMP"], "tesseract_setup.exe")
    subprocess.run(["curl", "-L", url, "-o", instalador], check=True)
    subprocess.run([instalador, "/S", "/Lang=eng"], check=True)
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    print("✔ Tesseract instalado com sucesso.")

# ─────────────────────────────────────────────
# Modelo de dados
# ─────────────────────────────────────────────

@dataclass
class NotaFiscal:
    numero: Optional[str]        = None
    data_emissao: Optional[str]  = None
    cnpj_emitente: Optional[str] = None
    nome_emitente: Optional[str] = None
    valor_total: Optional[float] = None
    impostos: Optional[float]    = None
    fonte: Optional[str]         = None   # "nativo" ou "ocr"
    confidence_score: dict       = field(default_factory=dict)


# ─────────────────────────────────────────────
# Rota 1 — PDF com texto nativo
# ─────────────────────────────────────────────

def extrair_pdf_nativo(caminho_pdf: str) -> str:
    """Extrai texto de um PDF que já contém texto selecionável."""
    texto_completo = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo += texto + "\n"
    return texto_completo


# ─────────────────────────────────────────────
# Rota 2 — PDF escaneado ou imagem
# ─────────────────────────────────────────────

def extrair_pdf_escaneado(caminho_pdf: str) -> str:
    """
    Converte cada página do PDF em imagem (300 DPI),
    pré-processa e aplica OCR em português.
    """
    paginas = convert_from_path(caminho_pdf, dpi=300)
    texto_completo = ""
    for pagina in paginas:
        imagem = pre_processar_imagem(pagina)
        texto = pytesseract.image_to_string(imagem, lang="eng")
        texto_completo += texto + "\n"
    return texto_completo


def extrair_imagem(caminho_imagem: str) -> str:
    img = cv2.imdecode(
        np.fromfile(caminho_imagem, dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE
    )
    # converte para PIL para passar ao pre_processar
    from PIL import Image
    imagem_pil = Image.fromarray(img)
    binarizado = pre_processar_imagem(imagem_pil)

    # PSM 6 = assume bloco de texto uniforme (ideal para cupom fiscal)
    config = "--psm 6 --oem 3"
    return pytesseract.image_to_string(binarizado, lang="eng", config=config)

# ─────────────────────────────────────────────
# Parsing com regex
# ─────────────────────────────────────────────

def parsear_nota(texto: str) -> NotaFiscal:
    nf = NotaFiscal()

    # CNPJ — aceita variações de caracteres que o OCR distorce
    match = re.search(r'\d{2}[\.,]\d{3}[\.,]\d{3}[/|\\]\d{4}[-]\d{2}', texto)
    if match:
        nf.cnpj_emitente = match.group()
        nf.confidence_score['cnpj'] = 1.0
    else:
        nf.confidence_score['cnpj'] = 0.0

    # Número da NF — "NFC-e no 37072" mas OCR pode ler "KFC-e" ou "NFC"
    match = re.search(r'[NKM]FC-e\s+n[oº°0]\s*(\d+)', texto, re.IGNORECASE)
    if match:
        nf.numero = match.group(1)
        nf.confidence_score['numero'] = 1.0
    else:
        nf.confidence_score['numero'] = 0.0

    # Data — DD/MM/AAAA (já funcionava)
    match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    if match:
        nf.data_emissao = match.group(1)
        nf.confidence_score['data_emissao'] = 1.0
    else:
        nf.confidence_score['data_emissao'] = 0.0

# Valor total — tenta múltiplos padrões pois o OCR distorce bastante
    for padrao in [
        r'Valor\s+Total\s+R[S$][\s\n]+([\d]+[,\.]\d{2})',   # linha separada
        r'Valor\s+Total\s+R[S$]\s*([\d]+[,\.]\d{2})',        # mesma linha
        r'Valor\s+a\s+Pagar\s+R[S$][\s\n]+([\d]+[,\.]\d{2})', # usa "Valor a Pagar"
    ]:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            valor_str = match.group(1).replace('.', '').replace(',', '.')
            nf.valor_total = float(valor_str)
            nf.confidence_score['valor_total'] = 1.0
            break
    else:
        nf.confidence_score['valor_total'] = 0.0

    # Impostos — "RS0,00" ou "R$0,00" colado na linha de tributos
    match = re.search(
        r'Tributos\s+Totais[^\n]*\n\s*R[S$]?\s*([\d]+[,\.]\d{2})',
        texto, re.IGNORECASE
    )
    if match:
        imposto_str = match.group(1).replace('.', '').replace(',', '.')
        nf.impostos = float(imposto_str)
        nf.confidence_score['impostos'] = 1.0
    else:
        nf.confidence_score['impostos'] = 0.0

    return nf

# ─────────────────────────────────────────────
# Ponto de entrada principal
# ─────────────────────────────────────────────

def pre_processar_imagem(imagem_pil) -> np.ndarray:
    img = np.array(imagem_pil)

    # Verifica quantos canais a imagem tem antes de converter
    if len(img.shape) == 3 and img.shape[2] == 3:
        cinza = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    elif len(img.shape) == 3 and img.shape[2] == 4:
        cinza = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
    else:
        cinza = img  # já está em escala de cinza, usa direto

    _, mascara = cv2.threshold(cinza, 100, 255, cv2.THRESH_BINARY)

    # 1. Remove fundo escuro — mantém só a região clara da nota
    _, mascara = cv2.threshold(cinza, 100, 255, cv2.THRESH_BINARY)
    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contornos:
        maior = max(contornos, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(maior)
        # só recorta se o contorno for grande o suficiente (evita recortar ruído)
        if w * h > (img.shape[0] * img.shape[1] * 0.1):
            cinza = cinza[y:y+h, x:x+w]

    # 2. Aumenta resolução (upscale) — ajuda o Tesseract em fontes pequenas
    cinza = cv2.resize(cinza, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 3. Melhora contraste com equalização adaptativa (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cinza = clahe.apply(cinza)

    # 4. Binarização adaptativa
    binarizado = cv2.adaptiveThreshold(
        cinza, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=15
    )

    return binarizado

def processar_nota_fiscal(caminho: str) -> NotaFiscal:
    extensao = caminho.lower().split('.')[-1]

    if extensao in ('jpg', 'jpeg', 'png', 'tiff', 'bmp'):
        texto = extrair_imagem(caminho)
        fonte = "ocr"
    elif extensao == 'pdf':
        with pdfplumber.open(caminho) as pdf:
            texto_teste = pdf.pages[0].extract_text() or ""
        if len(texto_teste.strip()) > 50:
            texto = extrair_pdf_nativo(caminho)
            fonte = "nativo"
        else:
            texto = extrair_pdf_escaneado(caminho)
            fonte = "ocr"
    else:
        raise ValueError(f"Formato não suportado: .{extensao}")

    nf = parsear_nota(texto)
    nf.fonte = fonte

    print("\n===== TEXTO EXTRAÍDO PELO OCR =====")
    print(texto)
    print("===================================\n")

    return nf

# ─────────────────────────────────────────────
# Execução direta (teste rápido)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import tkinter as tk
    from tkinter import filedialog

    # Garante que o Tesseract está instalado antes de qualquer coisa
    verificar_tesseract()

    # Se passou o caminho direto no terminal, usa ele
    # Senão, abre o seletor visual de arquivo
    if len(sys.argv) >= 2:
        caminho = sys.argv[1]
    else:
        root = tk.Tk()
        root.withdraw()
        caminho = filedialog.askopenfilename(
            title="Selecione a nota fiscal",
            filetypes=[
                ("Arquivos suportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.bmp"),
                ("PDF", "*.pdf"),
                ("Imagens", "*.jpg *.jpeg *.png *.tiff *.bmp"),
            ]
        )

    if not caminho:
        print("Nenhum arquivo selecionado.")
        sys.exit(1)

    print(f"\nProcessando: {caminho}")
    print("-" * 40)

    nota = processar_nota_fiscal(caminho)

    print(f"Fonte da extração : {nota.fonte}")
    print(f"Número da NF      : {nota.numero}")
    print(f"Data de emissão   : {nota.data_emissao}")
    print(f"CNPJ emitente     : {nota.cnpj_emitente}")
    print(f"Valor total       : R$ {nota.valor_total}")
    print(f"Impostos          : R$ {nota.impostos}")
    print(f"\nConfidence scores : {nota.confidence_score}")
