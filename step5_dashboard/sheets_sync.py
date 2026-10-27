"""
step5_dashboard/sheets_sync.py
------------------------------
Espelha a base SQLite em uma planilha do Google Sheets (fonte para o Looker Studio).

A sincronização é de mão única (base → planilha) e sempre reescreve as abas inteiras:
apagar a planilha e sincronizar de novo recria tudo, sem duplicar linhas, com
poucas chamadas à API (uma limpeza + uma escrita por aba).

Configuração (arquivo .env na raiz do projeto, veja .env.exemplo):
  GOOGLE_SHEET_ID      → trecho da URL da planilha entre /d/ e /edit
  GOOGLE_CREDENTIALS   → caminho do JSON da conta de serviço
                         (padrão: credenciais/google-service-account.json)
"""

import os

import pandas as pd

from step5_dashboard import analytics, database
from step5_dashboard.exportacao import _formatar_cnpj

CREDENCIAIS_PADRAO = os.path.join("credenciais", "google-service-account.json")

ABAS = ("Notas", "Itens", "Resumo Mensal")


def _carregar_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def configuracao() -> dict:
    """Lê o ID da planilha e o caminho da chave; não valida nada."""
    _carregar_env()
    return {
        "sheet_id": os.getenv("GOOGLE_SHEET_ID", "").strip(),
        "credenciais": os.getenv("GOOGLE_CREDENTIALS", CREDENCIAIS_PADRAO).strip(),
    }


def configurado() -> bool:
    cfg = configuracao()
    return bool(cfg["sheet_id"]) and os.path.exists(cfg["credenciais"])


# ─────────────────────────────────────────────
# Montagem das tabelas (sem acesso à rede)
# ─────────────────────────────────────────────

def _data_iso(serie: pd.Series) -> list:
    # Texto AAAA-MM-DD: o Looker Studio reconhece como data, e o Sheets não reinterpreta
    return [d.strftime("%Y-%m-%d") if pd.notna(d) else "" for d in serie]


def _celulas(df: pd.DataFrame) -> list[list]:
    """Cabeçalho + linhas, trocando NaN/None por vazio (a API do Sheets não aceita NaN)."""
    linhas = df.astype(object).where(df.notna(), "").values.tolist()
    return [list(df.columns)] + linhas


def montar_tabelas(notas: pd.DataFrame, itens: pd.DataFrame) -> dict[str, list[list]]:
    """Valores de cada aba, prontos para enviar."""
    qtd_itens = itens.groupby("nota_id").size()
    aba_notas = pd.DataFrame({
        "id": notas["id"],
        "numero_nf": notas["numero"],
        "data_emissao": _data_iso(notas["data_emissao"]),
        "cnpj_emitente": notas["cnpj_emitente"].map(_formatar_cnpj),
        "fornecedor": notas["nome_emitente"],
        "valor_total": notas["valor_total"],
        "impostos": notas["impostos"],
        "qtd_itens": notas["id"].map(qtd_itens).fillna(0).astype(int),
        "rota_leitura": notas["rota"],
        "confianca": notas["confianca"],
        "data_processamento": notas["data_processamento"],
    })
    aba_itens = pd.DataFrame({
        "nota_id": itens["nota_id"],
        "numero_nf": itens["numero"],
        "data_emissao": _data_iso(itens["data_emissao"]),
        "fornecedor": itens["nome_emitente"],
        "descricao": itens["descricao"],
        "valor": itens["valor"],
    })
    mensal = analytics.gasto_mensal(notas)
    aba_mensal = pd.DataFrame({
        "mes": _data_iso(mensal["mes"]),
        "gasto": mensal["gasto"],
        "impostos": mensal["impostos"],
        "qtd_notas": mensal["qtd_notas"],
    })
    return {
        "Notas": _celulas(aba_notas),
        "Itens": _celulas(aba_itens),
        "Resumo Mensal": _celulas(aba_mensal),
    }


# ─────────────────────────────────────────────
# Envio
# ─────────────────────────────────────────────

def _aba(planilha, nome: str, linhas: int, colunas: int):
    import gspread

    try:
        return planilha.worksheet(nome)
    except gspread.WorksheetNotFound:
        return planilha.add_worksheet(title=nome, rows=max(linhas, 100), cols=max(colunas, 10))


def sincronizar(caminho_banco: str = database.CAMINHO_BANCO, sheet_id: str = None, credenciais: str = None) -> dict:
    """
    Reescreve as abas Notas, Itens e Resumo Mensal com o conteúdo da base.
    Retorna o nº de linhas enviadas por aba.
    """
    import gspread

    cfg = configuracao()
    sheet_id = sheet_id or cfg["sheet_id"]
    credenciais = credenciais or cfg["credenciais"]
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID não definido no .env")
    if not os.path.exists(credenciais):
        raise FileNotFoundError(f"Chave da conta de serviço não encontrada: {credenciais}")

    tabelas = montar_tabelas(database.carregar_notas(caminho_banco), database.carregar_itens(caminho_banco))

    cliente = gspread.service_account(filename=credenciais)
    planilha = cliente.open_by_key(sheet_id)
    enviados = {}
    for nome, valores in tabelas.items():
        ws = _aba(planilha, nome, len(valores), len(valores[0]))
        ws.clear()
        ws.update(values=valores, range_name="A1", value_input_option="RAW")
        ws.freeze(rows=1)
        enviados[nome] = len(valores) - 1
    return enviados


# ─────────────────────────────────────────────
# Execução direta
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    banco = sys.argv[1] if len(sys.argv) > 1 else database.CAMINHO_BANCO
    try:
        resultado = sincronizar(banco)
    except Exception as e:
        print(f"❌ Erro na sincronização: {e}")
        sys.exit(1)
    for aba, qtd in resultado.items():
        print(f"✅ {aba}: {qtd} linha(s)")
