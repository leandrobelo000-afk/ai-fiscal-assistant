"""
step3_spreadsheet/writer.py
---------------------------
Grava os dados extraídos pela Etapa 2 no banco de dados SQLite.

Mantém compatibilidade com a API original:
- gravar_nota(nota, caminho_arquivo=None) -> bool

A planilha Excel foi substituída por SQLite para melhor performance e confiabilidade.
"""

import os
import sys
from datetime import datetime

# Configuração via .env
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

CAMINHO_PLANILHA_PADRAO = settings.CAMINHO_PLANILHA

# Importa o novo módulo de banco de dados
try:
    from step3_database import gravar_nota as db_gravar_nota, init_db, ja_existe
    USAR_SQLITE = True
except ImportError:
    USAR_SQLITE = False
    print("  [AVISO] Módulo step3_database não encontrado, usando fallback Excel (openpyxl)")


def verificar_dependencias():
    import importlib, subprocess
    for lib in ["pandas", "openpyxl"]:
        try:
            importlib.import_module(lib)
        except ImportError:
            subprocess.run([sys.executable, "-m", "pip", "install", lib], check=True)


# ─────────────────────────────────────────────
# Configuração (mantida para compatibilidade)
# ─────────────────────────────────────────────

def selecionar_caminho_planilha() -> str:
    """Abre seletor para escolher onde salvar ou abrir a planilha."""
    pass  # Não usado com SQLite

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

COLUNAS_ITENS = [
    "Número NF",
    "Data Emissão",
    "Nome Emitente",
    "Descrição Item",
    "Valor Item (R$)",
]


# ─────────────────────────────────────────────
# Funções de compatibilidade (fallback Excel)
# ─────────────────────────────────────────────

COR_CABECALHO   = "2D6A9F"
COR_CABECALHO_2 = "1A5276"
COR_FONTE       = "FFFFFF"


def _estilizar_cabecalho(ws, colunas: list, cor: str):
    """Aplica estilo ao cabeçalho de uma aba (fallback Excel)."""
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    for col_idx, nome in enumerate(colunas, start=1):
        celula = ws.cell(row=1, column=col_idx, value=nome)
        celula.font      = Font(bold=True, color=COR_FONTE, name="Arial", size=11)
        celula.fill      = PatternFill("solid", start_color=cor)
        celula.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_idx)].width = max(len(nome) + 4, 16)
    ws.row_dimensions[1].height = 28


def ja_existe_excel(numero_nf: str, caminho_planilha: str) -> bool:
    """Verifica se a nota já foi registrada na planilha (fallback)."""
    if not os.path.exists(caminho_planilha):
        return False
    try:
        import pandas as pd
        df = pd.read_excel(caminho_planilha, sheet_name="Resumo")
        if "Número NF" in df.columns:
            return str(numero_nf) in df["Número NF"].astype(str).values
    except Exception:
        pass
    return False


def criar_planilha(caminho_planilha):
    """Cria a planilha com as duas abas e cabeçalhos formatados (fallback)."""
    from openpyxl import Workbook
    wb = Workbook()
    ws_resumo = wb.active
    ws_resumo.title = "Resumo"
    _estilizar_cabecalho(ws_resumo, COLUNAS_RESUMO, COR_CABECALHO)
    ws_itens = wb.create_sheet("Itens")
    _estilizar_cabecalho(ws_itens, COLUNAS_ITENS, COR_CABECALHO_2)
    wb.save(caminho_planilha)
    print(f"  [INFO] Planilha criada em: {caminho_planilha}")


def gravar_nota_excel(nota, caminho_planilha=CAMINHO_PLANILHA_PADRAO) -> bool:
    """
    Fallback: grava na planilha Excel (código original mantido para compatibilidade).
    """
    if nota.numero and ja_existe_excel(nota.numero, caminho_planilha):
        print(f"  ⚠  NF {nota.numero} já registrada — ignorando.")
        return False

    if not os.path.exists(caminho_planilha):
        criar_planilha(caminho_planilha)

    from openpyxl import load_workbook
    wb = load_workbook(caminho_planilha)
    ws_resumo = wb["Resumo"]
    ws_itens  = wb["Itens"]

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

    ultima_linha = ws_resumo.max_row
    if ultima_linha % 2 == 0:
        from openpyxl.styles import PatternFill
        cor_linha = "EBF5FB"
        for col in range(1, len(COLUNAS_RESUMO) + 1):
            ws_resumo.cell(ultima_linha, col).fill = PatternFill("solid", start_color=cor_linha)

    for item in nota.itens:
        ws_itens.append([
            nota.numero,
            nota.data_emissao,
            nota.nome_emitente,
            item.get("descricao"),
            item.get("valor"),
        ])

    total_row = ws_resumo.max_row + 2
    ws_resumo.cell(total_row, 5, "TOTAL GERAL").font = Font(bold=True, name="Arial")
    ws_resumo.cell(total_row, 6, f"=SUM(F2:F{ws_resumo.max_row - 1})").font = Font(bold=True, name="Arial")

    wb.save(caminho_planilha)
    print(f"  [OK] NF {nota.numero or 'sem número'} gravada com sucesso (Excel).")
    return True


# ─────────────────────────────────────────────
# API Principal - Usa SQLite por padrão
# ─────────────────────────────────────────────

def gravar_nota(nota, caminho_arquivo=CAMINHO_PLANILHA_PADRAO) -> bool:
    """
    Recebe um objeto NotaFiscalProcessada (Etapa 2) e grava no banco SQLite.
    Retorna True se gravou, False se a nota já existia.

    Args:
        nota: Objeto NotaFiscalProcessada
        caminho_arquivo: Caminho do banco de dados (ignorado se não for .db)

    Mantém a mesma assinatura da versão original para compatibilidade.
    """
    # Se o caminho terminar em .db, usa como banco SQLite
    # Caso contrário, usa o banco padrão
    if caminho_arquivo and caminho_arquivo.endswith(".db"):
        db_path = caminho_arquivo
    else:
        # Se for caminho de Excel, converte para .db no mesmo diretório
        if caminho_arquivo and caminho_arquivo.endswith(".xlsx"):
            db_path = caminho_arquivo.replace(".xlsx", ".db")
        else:
            db_path = CAMINHO_PLANILHA_PADRAO.replace(".xlsx", ".db")

    # Usa SQLite se disponível
    if USAR_SQLITE:
        return db_gravar_nota(nota, db_path)

    # Fallback para Excel
    print("  ⚠ Usando fallback Excel (openpyxl)")
    return gravar_nota_excel(nota, caminho_arquivo)


# ─────────────────────────────────────────────
# Execução direta (mantida para testes)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from step1_ocr.extractor import verificar_tesseract
    from step2_llm.processor import processar_nota_fiscal
    import tkinter as tk
    from tkinter import filedialog

    verificar_tesseract()

    root = tk.Tk()
    root.withdraw()
    arquivos = filedialog.askopenfilenames(
        title="Selecione uma ou mais notas fiscais",
        filetypes=[("Arquivos suportados", "*.pdf *.jpg *.jpeg *.png *.tiff *.bmp")]
    )

    if not arquivos:
        print("Nenhum arquivo selecionado.")
        sys.exit(1)

    print(f"\n[INFO] {len(arquivos)} arquivo(s) selecionado(s)")
    print("=" * 50)

    gravadas = 0
    ignoradas = 0

    for caminho in arquivos:
        print(f"\n[INFO] {os.path.basename(caminho)}")
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
            print(f"  [ERRO] Erro ao processar: {e}")

    print("\n" + "=" * 50)
    print(f"[OK] Gravadas : {gravadas}")
    print(f"[AVISO] Ignoradas: {ignoradas} (duplicatas)")
    db_path = CAMINHO_PLANILHA_PADRAO.replace(".xlsx", ".db")
    print(f"[INFO] Banco de dados: {db_path}")