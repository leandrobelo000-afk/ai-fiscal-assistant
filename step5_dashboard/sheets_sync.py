"""
step5_dashboard/sheets_sync.py
------------------------------
Espelha a base SQLite em uma planilha do Google Sheets (fonte para o Looker Studio).

A sincronização é de mão única (base → planilha) e sempre reescreve as abas inteiras:
apagar a planilha e sincronizar de novo recria tudo, sem duplicar linhas, com
poucas chamadas à API (uma limpeza + uma escrita por aba).

Configuração: pela página "Google Sheets" do app (envia a chave JSON e cola o link
da planilha), que grava tudo em credenciais/google-sheets.json. Quem já usava o
.env continua funcionando: GOOGLE_SHEET_ID e GOOGLE_CREDENTIALS valem quando o app
não tem nada salvo.
"""

import json
import os
import re

import pandas as pd

from step5_dashboard import analytics, database
from step5_dashboard.exportacao import _formatar_cnpj

PASTA_CREDENCIAIS = "credenciais"
CREDENCIAIS_PADRAO = os.path.join(PASTA_CREDENCIAIS, "google-service-account.json")
ARQUIVO_CONFIG = os.path.join(PASTA_CREDENCIAIS, "google-sheets.json")

ABAS = ("Notas", "Itens", "Resumo Mensal")

LINK_CONTAS_SERVICO = "https://console.cloud.google.com/iam-admin/serviceaccounts"
LINK_API_SHEETS = "https://console.cloud.google.com/apis/library/sheets.googleapis.com"


# ─────────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────────

def _carregar_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _config_salva() -> dict:
    try:
        with open(ARQUIVO_CONFIG, encoding="utf-8") as f:
            dados = json.load(f)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _salvar_config(**valores):
    dados = _config_salva()
    dados.update(valores)
    os.makedirs(PASTA_CREDENCIAIS, exist_ok=True)
    with open(ARQUIVO_CONFIG, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)


def configuracao() -> dict:
    """ID da planilha e caminho da chave; o que foi salvo pelo app vale mais que o .env."""
    _carregar_env()
    salva = _config_salva()
    return {
        "sheet_id": (salva.get("sheet_id") or os.getenv("GOOGLE_SHEET_ID", "")).strip(),
        "credenciais": (salva.get("credenciais") or os.getenv("GOOGLE_CREDENTIALS", "")
                        or CREDENCIAIS_PADRAO).strip(),
    }


def configurado() -> bool:
    cfg = configuracao()
    return bool(cfg["sheet_id"]) and os.path.exists(cfg["credenciais"])


def extrair_id(texto: str) -> str:
    """Aceita o link da planilha (como aparece no navegador) ou só o ID; '' se não reconhecer."""
    texto = (texto or "").strip()
    achado = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", texto)
    if achado:
        return achado.group(1)
    return texto if re.fullmatch(r"[a-zA-Z0-9_-]{20,}", texto) else ""


def link_planilha(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


def salvar_planilha(link_ou_id: str) -> str:
    """Guarda a planilha escolhida e devolve o ID tirado do link."""
    sheet_id = extrair_id(link_ou_id)
    if not sheet_id:
        raise ValueError("Não reconheci esse link. Copie o endereço da planilha direto da barra do navegador.")
    _salvar_config(sheet_id=sheet_id)
    return sheet_id


def ler_chave(conteudo: bytes) -> dict:
    """Confere se o JSON é a chave de uma conta de serviço e devolve o conteúdo."""
    try:
        chave = json.loads(conteudo)
    except ValueError:
        raise ValueError("O arquivo não é um JSON válido. Envie a chave baixada do Google Cloud.")
    if not isinstance(chave, dict) or chave.get("type") != "service_account" or not chave.get("client_email"):
        raise ValueError("Esse JSON não é a chave de uma conta de serviço. No Google Cloud, abra a conta "
                         "de serviço > Chaves > Adicionar chave > Criar nova chave > JSON.")
    return chave


def salvar_chave(conteudo: bytes) -> str:
    """Grava a chave na pasta credenciais (fora do Git) e devolve o e-mail da conta de serviço."""
    chave = ler_chave(conteudo)
    os.makedirs(PASTA_CREDENCIAIS, exist_ok=True)
    with open(CREDENCIAIS_PADRAO, "wb") as f:
        f.write(conteudo)
    _salvar_config(credenciais=CREDENCIAIS_PADRAO)
    return chave["client_email"]


def dados_chave() -> dict:
    """Conteúdo da chave configurada ({} se não houver ou for inválida)."""
    try:
        with open(configuracao()["credenciais"], "rb") as f:
            return ler_chave(f.read())
    except (OSError, ValueError):
        return {}


def mensagem_amigavel(erro: Exception) -> str:
    """Traduz os erros mais comuns do Google para o que o usuário precisa fazer."""
    import gspread

    chave = dados_chave()
    email = chave.get("client_email", "o e-mail da conta de serviço")
    texto = f"{erro} {erro.__cause__ or ''}"
    if "SERVICE_DISABLED" in texto or "has not been used" in texto or "is disabled" in texto:
        link = f"{LINK_API_SHEETS}?project={chave['project_id']}" if chave.get("project_id") else LINK_API_SHEETS
        return f"A Google Sheets API está desligada no seu projeto. Ative em {link} e tente de novo em 1 minuto."
    if isinstance(erro, PermissionError):
        return f"A planilha não está compartilhada com {email}. Na planilha, clique em Compartilhar e adicione esse e-mail como Editor."
    if isinstance(erro, gspread.SpreadsheetNotFound):
        return f"Planilha não encontrada. Confira o link e se ela foi compartilhada com {email}."
    if "invalid_grant" in texto or "Invalid JWT" in texto:
        return "O Google recusou a chave (ela pode ter sido apagada). Gere uma chave JSON nova e envie de novo."
    if isinstance(erro, (ValueError, FileNotFoundError)):
        return str(erro)
    return f"Não foi possível falar com o Google Sheets: {erro}"


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

def _abrir_planilha(sheet_id: str = None, credenciais: str = None):
    import gspread

    cfg = configuracao()
    sheet_id = sheet_id or cfg["sheet_id"]
    credenciais = credenciais or cfg["credenciais"]
    if not sheet_id:
        raise ValueError("Nenhuma planilha escolhida. Cole o link dela na página Google Sheets do app.")
    if not os.path.exists(credenciais):
        raise FileNotFoundError("Chave da conta de serviço não encontrada. Envie o arquivo JSON na página Google Sheets do app.")
    return gspread.service_account(filename=credenciais).open_by_key(sheet_id)


def testar_conexao() -> str:
    """Abre a planilha configurada e devolve o título dela; erros vão para mensagem_amigavel."""
    return _abrir_planilha().title


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
    planilha = _abrir_planilha(sheet_id, credenciais)
    tabelas = montar_tabelas(database.carregar_notas(caminho_banco), database.carregar_itens(caminho_banco))
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
        print(f"❌ Erro na sincronização: {mensagem_amigavel(e)}")
        sys.exit(1)
    for aba, qtd in resultado.items():
        print(f"✅ {aba}: {qtd} linha(s)")
