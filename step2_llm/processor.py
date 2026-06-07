"""
step2_llm/processor.py
----------------------
Nova abordagem: a LLM recebe a imagem diretamente (Vision).
O Tesseract só é usado como fallback se a confiança for baixa.

Fluxo:
  1. Imagem da NF é enviada diretamente ao Qwen2.5-VL (Vision)
  2. Modelo extrai e estrutura os dados em JSON
  3. Se confiança for baixa → Tesseract extrai texto → LLM processa o texto
"""

import os
import sys
import json
import re
import base64
import requests
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────

LM_STUDIO_URL    = "http://localhost:1234/v1/chat/completions"
MODELO           = "qwen2.5-vl-3b-instruct"


# ─────────────────────────────────────────────
# Modelo de dados
# ─────────────────────────────────────────────

@dataclass
class NotaFiscalProcessada:
    numero:        Optional[str]   = None
    data_emissao:  Optional[str]   = None
    cnpj_emitente: Optional[str]   = None
    nome_emitente: Optional[str]   = None
    valor_total:   Optional[float] = None
    impostos:      Optional[float] = None
    itens:         list            = field(default_factory=list)
    rota:          str             = "vision"   # "vision" ou "vision+ocr"
    confianca:     str             = "alta"     # "alta", "media", "baixa"


# ─────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """Você é um assistente especializado em leitura de notas fiscais brasileiras.
Analise a imagem ou texto fornecido e extraia os campos da nota fiscal.

PRIORIDADE DOS CAMPOS (extraia nesta ordem):
1. numero, data_emissao, cnpj_emitente, nome_emitente
2. valor_total, impostos
3. itens (resuma em no máximo 5 itens principais)
4. O número da NF aparece após "NFC-e no" ou "Número" na nota

REGRAS:
- Responda APENAS com JSON válido, sem texto adicional, sem markdown
- Se um campo não for encontrado, use null
- CNPJ deve estar no formato XX.XXX.XXX/XXXX-XX
- Data deve estar no formato DD/MM/AAAA
- Valores devem ser números float (ex: 117.14)
- itens: máximo 5 itens, extraia apenas descricao e VL.TOTAL (último valor da linha), ignorando quantidade e VL.UNIT
- confianca: "alta" se leu bem, "media" se teve dificuldade, "baixa" se ilegível
- O número da NF aparece após "NFC-e no" ou "Número" na nota fiscal
- Em itens, o campo "valor" deve ser o VL.TOTAL (último valor da linha), nunca a quantidade
- impostos: se a linha de tributos mostrar 0,00 ou R$0,00, retorne 0.0 (não null)
- numero: procure por "NFC-e no XXXXX" ou "NF-e nº XXXXX" na parte inferior da nota

FORMATO DE RESPOSTA:
{
  "numero": "string ou null",
  "data_emissao": "DD/MM/AAAA ou null",
  "cnpj_emitente": "XX.XXX.XXX/XXXX-XX ou null",
  "nome_emitente": "string ou null",
  "valor_total": float ou null,
  "impostos": float ou null,
  "itens": [{"descricao": "string", "valor": float}],
  "confianca": "alta|media|baixa"
}"""

PROMPT_VISION = "Extraia todos os dados desta nota fiscal. Responda apenas com o JSON."


def PROMPT_TEXTO(texto):
    return f"Extraia os dados desta nota fiscal. O texto foi obtido por OCR e pode ter erros:\n\n{texto}\n\nResponda apenas com o JSON."


# ─────────────────────────────────────────────
# Utilitários
# ─────────────────────────────────────────────

def verificar_servidor() -> bool:
    try:
        r = requests.get("http://localhost:1234/v1/models", timeout=3)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def imagem_para_base64(caminho: str) -> tuple:
    """Converte imagem para base64 e detecta o media_type."""
    ext = caminho.lower().split(".")[-1]
    tipos = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png",  "bmp": "image/bmp",
        "tiff": "image/tiff","webp": "image/webp"
    }
    media_type = tipos.get(ext, "image/jpeg")
    with open(caminho, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, media_type


def parse_json(conteudo: str) -> dict:
    """Remove blocos markdown, tenta parse e corrige JSON incompleto."""
    conteudo = re.sub(r"```(?:json)?", "", conteudo).strip("`").strip()

    # Tenta parse normal primeiro
    try:
        return json.loads(conteudo)
    except json.JSONDecodeError:
        pass

    # JSON incompleto — tenta fechar automaticamente
    try:
            # Fecha listas e objetos abertos
            abertas_chaves = conteudo.count("{") - conteudo.count("}")
            abertas_colchetes = conteudo.count("[") - conteudo.count("]")

            # Remove última linha incompleta (sem vírgula ou sem fechamento)
            linhas = conteudo.strip().splitlines()
            while linhas and not linhas[-1].strip().endswith(('"', '}', ']', 'null', 'true', 'false')) and not linhas[-1].strip()[-1:].isdigit():
                linhas.pop()
            conteudo = "\n".join(linhas)

            # Remove vírgula final se existir
            conteudo = re.sub(r",\s*$", "", conteudo.strip())

            # Fecha estruturas abertas
            conteudo += "]" * abertas_colchetes
            conteudo += "}" * abertas_chaves

            return json.loads(conteudo)
    except Exception:
        # Último recurso — retorna o que conseguiu extrair via regex
        print("  ⚠ JSON corrompido — extraindo campos manualmente...")
        return {
            "numero":        re.search(r'"numero"\s*:\s*"([^"]+)"', conteudo) and re.search(r'"numero"\s*:\s*"([^"]+)"', conteudo).group(1),
            "data_emissao":  re.search(r'"data_emissao"\s*:\s*"([^"]+)"', conteudo) and re.search(r'"data_emissao"\s*:\s*"([^"]+)"', conteudo).group(1),
            "cnpj_emitente": re.search(r'"cnpj_emitente"\s*:\s*"([^"]+)"', conteudo) and re.search(r'"cnpj_emitente"\s*:\s*"([^"]+)"', conteudo).group(1),
            "nome_emitente": re.search(r'"nome_emitente"\s*:\s*"([^"]+)"', conteudo) and re.search(r'"nome_emitente"\s*:\s*"([^"]+)"', conteudo).group(1),
            "valor_total":   float(re.search(r'"valor_total"\s*:\s*([\d.]+)', conteudo).group(1)) if re.search(r'"valor_total"\s*:\s*([\d.]+)', conteudo) else None,
            "impostos":      float(re.search(r'"impostos"\s*:\s*([\d.]+)', conteudo).group(1)) if re.search(r'"impostos"\s*:\s*([\d.]+)', conteudo) else None,
            "itens":         [],
            "confianca":     "media",
        }


def montar_nota(dados: dict, rota: str) -> NotaFiscalProcessada:
    return NotaFiscalProcessada(
        numero        = dados.get("numero"),
        data_emissao  = dados.get("data_emissao"),
        cnpj_emitente = dados.get("cnpj_emitente"),
        nome_emitente = dados.get("nome_emitente"),
        valor_total   = dados.get("valor_total"),
        impostos      = dados.get("impostos"),
        itens         = dados.get("itens", []),
        confianca     = dados.get("confianca", "media"),
        rota          = rota,
    )


# ─────────────────────────────────────────────
# Rota 1 — Vision direto
# ─────────────────────────────────────────────

def chamar_llm_vision(caminho_imagem: str) -> dict:
    """Envia a imagem diretamente ao modelo Vision."""
    b64, media_type = imagem_para_base64(caminho_imagem)

    payload = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": PROMPT_VISION}
            ]}
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }

    resposta = requests.post(LM_STUDIO_URL, json=payload, timeout=120)
    resposta.raise_for_status()
    conteudo = resposta.json()["choices"][0]["message"]["content"].strip()
    return parse_json(conteudo)


# ─────────────────────────────────────────────
# Rota 2 — Fallback: Tesseract + LLM
# ─────────────────────────────────────────────

def extrair_com_tesseract(caminho: str) -> str:
    """Fallback: extrai texto bruto com Tesseract."""
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image
    from step1_ocr.extractor import pre_processar_imagem

    img = cv2.imdecode(np.fromfile(caminho, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    imagem_pil = Image.fromarray(img)
    binarizado = pre_processar_imagem(imagem_pil)
    return pytesseract.image_to_string(binarizado, lang="eng", config="--psm 6 --oem 3")


def chamar_llm_texto(texto_ocr: str) -> dict:
    """Envia texto extraído pelo Tesseract ao modelo."""
    payload = {
        "model": MODELO,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": PROMPT_TEXTO(texto_ocr)}
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }

    resposta = requests.post(LM_STUDIO_URL, on=payload, timeout=60)
    resposta.raise_for_status()
    conteudo = resposta.json()["choices"]["0 message"]["content"].strip()
    return parse_json(conteudo)


# ───────────────────────────────────────── ─
# Ponto de entrada principal
# ─────────────────────────────────────────────

def processar_nota_fiscal(caminho: str) -> NotaFiscalProcessada:
    """
    Fluxo principal:
      1. LLM Vision lê a imagem diretamente
      2. Tesseract complementa campos que a Vision não encontrou
    """
    if not verificar_servidor():
        raise ConnectionError(
            "Servidor LM Studio não encontrado em localhost:1234.\n"
            "Inicie com: lms server start"
        )

    # Rota 1 — Vision
    print("  👁  Enviando imagem para o modelo Vision...")
    dados = chamar_llm_vision(caminho)
    nota  = montar_nota(dados, rota="vision")

    # Complementa com Tesseract apenas os campos ausentes
    campos_ausentes = [
        k for k, v in {
            "numero": nota.numero,
            "impostos": nota.impostos,
        }.items() if v is None
    ]

    if campos_ausentes:
        print(f"  🔍 Complementando com Tesseract: {campos_ausentes}...")
        import re
        texto_ocr = extrair_com_tesseract(caminho)

        if "numero" in campos_ausentes:
            match = re.search(r'[NKM]FC-e\s+n[oº°0]\s*(\d+)', texto_ocr, re.IGNORECASE)
            if match:
                nota.numero = match.group(1)
                print(f"  ✔ Número encontrado pelo Tesseract: {nota.numero}")

        if "impostos" in campos_ausentes:
            match = re.search(r'Tributos\s+Totais[^\n]*\n\s*R[S$]?\s*([\d]+[,\.]\d{2})', texto_ocr, re.IGNORECASE)
            if match:
                nota.impostos = float(match.group(1).replace('.', '').replace(',', '.'))
                print(f"  ✔ Impostos encontrados pelo Tesseract: {nota.impostos}")
            else:
                nota.impostos = 0.0  # tributos zero é comum em NFC-e

        nota.rota = "vision+tesseract"

    return nota


# ─────────────────────────────────────────────
# Execução direta
# ─────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from step1_ocr.extractor import verificar_tesseract
    import tkinter as tk
    from tkinter import filedialog

    verificar_tesseract()

    root = tk.Tk()
    root.withdraw()
    caminho = filedialog.askopenfilename(
        title="Selecione a nota fiscal",
        filetypes=[("Arquivos suportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.bmp")]
    )

    if not caminho:
        print("Nenhum arquivo selecionado.")
        sys.exit(1)

    print(f"\n📄 Arquivo: {caminho}")
    print("-" * 40)

    nota = processar_nota_fiscal(caminho)

    print(f"\n✅ Resultado (rota: {nota.rota}):")
    print(f"  Número da NF  : {nota.numero}")
    print(f"  Data emissão  : {nota.data_emissao}")
    print(f"  CNPJ emitente : {nota.cnpj_emitente}")
    print(f"  Nome emitente : {nota.nome_emitente}")
    print(f"  Valor total   : R$ {nota.valor_total}")
    print(f"  Impostos      : R$ {nota.impostos}")
    print(f"  Confiança     : {nota.confianca}")
    if nota.itens:
        print(f"  Itens ({len(nota.itens)}):")
        for item in nota.itens[:5]:
            print(f"    - {item.get('descricao')} → R$ {item.get('valor')}")