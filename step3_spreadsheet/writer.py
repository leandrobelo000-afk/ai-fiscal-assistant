"""
step3_spreadsheet/writer.py
---------------------------
Grava os dados extraídos pela Etapa 2 em uma planilha Excel acumulativa.

Estrutura da planilha:
  - Aba "Resumo"  → uma linha por nota fiscal processada
  - Aba "Itens"   → todos os itens de todas as notas, com referência ao número da NF

A planilha é criada na primeira execução e acumulada nas seguintes —
novas notas são sempre adicionadas sem sobrescrever as anteriores.
"""

import os
import sys
import pandas as pd
from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime

def verificar_dependencias():
    import importlib, subprocess
    for lib in ["pandas", "openpyxl"]:
        try:
            importlib.import_module(lib)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", lib], check=True)


# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────

CAMINHO_PLANILHA = "notas_fiscais.xlsx"

COLUNAS_RESUMO = [
    "Data Processamento",
    "Número NF",
    "Data Emissão",
    "CNPJ Emitente",
    "Nome Emitente",
    "Valor Total (R$)",
    "Impostos (R$)",
    "Qtd Itens",
]

COLUNA_TOTAL = len(COLUNAS_RESUMO) + 2   # coluna J, separada por uma coluna vazia

COLUNAS_ITENS = [
    "Número NF",
    "Data Emissão",
    "Nome Emitente",
    "Descrição Item",
    "Valor Item (R$)",
]


# ─────────────────────────────────────────────
# Criação inicial da planilha
# ─────────────────────────────────────────────

COR_CABECALHO   = "2D6A9F"   # azul
COR_CABECALHO_2 = "1A5276"   # azul escuro para aba de itens
COR_FONTE       = "FFFFFF"   # branco


def _estilizar_cabecalho(ws, colunas: list, cor: str):
    """Aplica estilo ao cabeçalho de uma aba."""
    for col_idx, nome in enumerate(colunas, start=1):
        celula = ws.cell(row=1, column=col_idx, value=nome)
        celula.font      = Font(bold=True, color=COR_FONTE, name="Arial", size=11)
        celula.fill      = PatternFill("solid", start_color=cor)
        celula.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(nome) + 4, 16)
    ws.row_dimensions[1].height = 28

# ─────────────────────────────────────────────
# Verificação de duplicata
# ─────────────────────────────────────────────

def _so_digitos(valor) -> str:
    return "".join(c for c in str(valor) if c.isdigit()) if valor is not None else ""


def ja_existe(numero_nf: str, caminho_planilha: str, cnpj_emitente: str = None) -> bool:
    """
    Verifica se a nota já foi registrada na planilha.
    A mesma nota = mesmo número E mesmo CNPJ do emitente (fornecedores
    diferentes podem emitir notas com o mesmo número).
    """
    if not os.path.exists(caminho_planilha):
        return False
    try:
        df = pd.read_excel(caminho_planilha, sheet_name="Resumo", dtype=str)
        if "Número NF" not in df.columns:
            return False
        mesmo_numero = df["Número NF"].str.removesuffix(".0") == str(numero_nf)
        if cnpj_emitente is None or "CNPJ Emitente" not in df.columns:
            return bool(mesmo_numero.any())
        mesmo_cnpj = df["CNPJ Emitente"].map(_so_digitos) == _so_digitos(cnpj_emitente)
        return bool((mesmo_numero & mesmo_cnpj).any())
    except Exception:
        pass
    return False


def _remover_totais_antigos(ws):
    """
    Versões anteriores gravavam uma linha "TOTAL GERAL" (+ uma linha vazia) a cada nota,
    no meio dos dados. Remove essas linhas para o SUM da coluna J não contar em dobro.
    """
    for linha in range(ws.max_row, 1, -1):
        rotulo = ws.cell(linha, 5).value
        vazia = all(ws.cell(linha, c).value is None for c in range(1, len(COLUNAS_RESUMO) + 1))
        if rotulo == "TOTAL GERAL" or vazia:
            ws.delete_rows(linha)


# ─────────────────────────────────────────────
# Gravação dos dados
# ─────────────────────────────────────────────

def gravar_nota(nota, caminho_planilha=CAMINHO_PLANILHA) -> bool:
    """
    Recebe um objeto NotaFiscalProcessada (Etapa 2) e grava na planilha.
    Retorna True se gravou, False se a nota já existia.
    """
    # Verifica duplicata usando o caminho correto
    if nota.numero and ja_existe(nota.numero, caminho_planilha, nota.cnpj_emitente):
        print(f"  ⚠  NF {nota.numero} já registrada — ignorando.")
        return False

    # Cria planilha se não existir
    if not os.path.exists(caminho_planilha):
        criar_planilha(caminho_planilha)

    wb = load_workbook(caminho_planilha)
    ws_resumo = wb["Resumo"]
    ws_itens  = wb["Itens"]
    _remover_totais_antigos(ws_resumo)

    # Linha de resumo
    linha_resumo = [
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        nota.numero,
        nota.data_emissao,
        nota.cnpj_emitente,
        nota.nome_emitente,
        nota.valor_total,
        nota.impostos if nota.impostos is not None else 0.0,
        len(nota.itens),
    ]
    ws_resumo.append(linha_resumo)

    # Zebra stripes na aba Resumo
    ultima_linha = ws_resumo.max_row
    if ultima_linha % 2 == 0:
        cor_linha = "EBF5FB"
        for col in range(1, len(COLUNAS_RESUMO) + 1):
            ws_resumo.cell(ultima_linha, col).fill = PatternFill("solid", start_color=cor_linha)

    # Linhas de itens
    for item in nota.itens:
        ws_itens.append([
            nota.numero,
            nota.data_emissao,
            nota.nome_emitente,
            item.get("descricao"),
            item.get("valor"),
        ])

    # Total geral fora da área de dados (coluna J), para não se misturar com as notas
    # nem ser somado de novo a cada gravação. SUM(F:F) ignora o cabeçalho (texto).
    ws_resumo.cell(1, COLUNA_TOTAL, "TOTAL GERAL").font = Font(bold=True, name="Arial")
    ws_resumo.cell(2, COLUNA_TOTAL, "=SUM(F:F)").font = Font(bold=True, name="Arial")

    wb.save(caminho_planilha)
    print(f"  ✅ NF {nota.numero or 'sem número'} gravada com sucesso.")
    return True

def criar_planilha(caminho_planilha):
    """Cria a planilha com as duas abas e cabeçalhos formatados."""
    wb = Workbook()

    # Aba Resumo
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    _estilizar_cabecalho(ws_resumo, COLUNAS_RESUMO, COR_CABECALHO)

    # Aba Itens
    ws_itens = wb.create_sheet("Itens")
    _estilizar_cabecalho(ws_itens, COLUNAS_ITENS, COR_CABECALHO_2)

    wb.save(caminho_planilha)
    print(f"  📊 Planilha criada em: {caminho_planilha}")


# ─────────────────────────────────────────────
# Execução direta
# ─────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from step1_ocr.extractor import verificar_tesseract
    from step2_llm.processor import processar_nota_fiscal
    import tkinter as tk
    from tkinter import filedialog

    verificar_tesseract()

    # Permite selecionar múltiplos arquivos de uma vez
    root = tk.Tk()
    root.withdraw()
    arquivos = filedialog.askopenfilenames(
        title="Selecione uma ou mais notas fiscais",
        filetypes=[("Arquivos suportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.bmp")]
    )

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        sys.exit(1)

    print(f"\n📂 {len(arquivos)} arquivo(s) selecionado(s)")
    print("=" * 50)

    gravadas = 0
    ignoradas = 0

    for caminho in arquivos:
        print(f"\n📄 {os.path.basename(caminho)}")
        print("-" * 40)

        try:
            nota = processar_nota_fiscal(caminho)

            print(f"  Número : {nota.numero}")
            print(f"  Data   : {nota.data_emissao}")
            print(f"  CNPJ   : {nota.cnpj_emitente}")
            print(f"  Valor  : R$ {nota.valor_total}")
            print(f"  Rota   : {nota.rota} | Confiança: {nota.confianca}")

            resultado = gravar_nota(nota)
            if resultado:
                gravadas += 1
            else:
                ignoradas += 1

        except Exception as e:
            print(f"  ❌ Erro ao processar: {e}")

    print("\n" + "=" * 50)
    print(f"✅ Gravadas : {gravadas}")
    print(f"⚠  Ignoradas: {ignoradas} (duplicatas)")
    print(f"📊 Planilha : {CAMINHO_PLANILHA}")

