"""
step5_dashboard/database.py
---------------------------
Base SQLite que passa a ser a fonte única dos dados das notas fiscais.

Estrutura do banco:
  - Tabela "notas" → uma linha por nota fiscal, chave única (CNPJ emitente + número)
  - Tabela "itens" → itens de cada nota, ligados pelo id da nota

O Excel (Etapa 3) e, mais adiante, o Google Sheets passam a ser saídas
geradas a partir deste banco, e não mais o lugar onde os dados vivem.
"""

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime

import pandas as pd

CAMINHO_BANCO = "notas_fiscais.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS notas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero              TEXT,
    data_emissao        TEXT,      -- ISO: AAAA-MM-DD
    cnpj_emitente       TEXT,      -- só dígitos
    nome_emitente       TEXT,
    valor_total         REAL,
    impostos            REAL,
    rota                TEXT,
    confianca           TEXT,
    data_processamento  TEXT NOT NULL,
    UNIQUE (cnpj_emitente, numero)
);

CREATE TABLE IF NOT EXISTS itens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nota_id     INTEGER NOT NULL REFERENCES notas(id) ON DELETE CASCADE,
    descricao   TEXT,
    valor       REAL
);

CREATE INDEX IF NOT EXISTS idx_notas_data ON notas(data_emissao);
CREATE INDEX IF NOT EXISTS idx_itens_nota ON itens(nota_id);
"""


# ─────────────────────────────────────────────
# Normalização dos campos
# ─────────────────────────────────────────────

def normalizar_data(valor) -> str | None:
    """Converte DD/MM/AAAA (formato do LLM) ou datas do Excel para AAAA-MM-DD."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.strftime("%Y-%m-%d")
    texto = str(valor).strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, formato).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalizar_cnpj(valor) -> str | None:
    """Mantém só os dígitos, para que '12.345.678/0001-90' e '12345678000190' sejam iguais."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    digitos = re.sub(r"\D", "", str(valor))
    return digitos or None


def normalizar_valor(valor) -> float | None:
    """Aceita float, '117.14', '117,14' ou 'R$ 1.117,14'."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"[^\d,.\-]", "", str(valor))
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _texto(valor) -> str | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    # O Excel costuma devolver números de NF como float ("123.0")
    if re.fullmatch(r"\d+\.0", texto):
        texto = texto[:-2]
    return texto or None


# ─────────────────────────────────────────────
# Conexão
# ─────────────────────────────────────────────

def conectar(caminho_banco: str = CAMINHO_BANCO) -> sqlite3.Connection:
    """Abre o banco e cria as tabelas na primeira execução."""
    conexao = sqlite3.connect(caminho_banco)
    conexao.execute("PRAGMA foreign_keys = ON")
    conexao.executescript(SCHEMA)
    return conexao


@contextmanager
def sessao(caminho_banco: str = CAMINHO_BANCO):
    """Abre o banco, confirma a transação no fim e sempre fecha o arquivo."""
    conexao = conectar(caminho_banco)
    try:
        with conexao:
            yield conexao
    finally:
        conexao.close()


# ─────────────────────────────────────────────
# Gravação
# ─────────────────────────────────────────────

def ja_existe(conexao: sqlite3.Connection, cnpj_emitente, numero) -> bool:
    """Uma nota é a mesma quando o CNPJ do emitente e o número coincidem."""
    cnpj, num = normalizar_cnpj(cnpj_emitente), _texto(numero)
    if num is None:
        return False
    linha = conexao.execute(
        "SELECT 1 FROM notas WHERE numero = ? AND cnpj_emitente IS ?", (num, cnpj)
    ).fetchone()
    return linha is not None


def salvar_nota(nota, caminho_banco: str = CAMINHO_BANCO, data_processamento: str | None = None) -> bool:
    """
    Recebe um NotaFiscalProcessada (Etapa 2) e grava no banco.
    Retorna True se gravou, False se a nota já existia.
    """
    with sessao(caminho_banco) as conexao:
        return _inserir(conexao, nota, data_processamento)


def _inserir(conexao, nota, data_processamento=None) -> bool:
    if ja_existe(conexao, nota.cnpj_emitente, nota.numero):
        return False

    cursor = conexao.execute(
        """INSERT INTO notas (numero, data_emissao, cnpj_emitente, nome_emitente,
                              valor_total, impostos, rota, confianca, data_processamento)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _texto(nota.numero),
            normalizar_data(nota.data_emissao),
            normalizar_cnpj(nota.cnpj_emitente),
            _texto(nota.nome_emitente),
            normalizar_valor(nota.valor_total),
            normalizar_valor(nota.impostos) if nota.impostos is not None else 0.0,
            getattr(nota, "rota", None),
            getattr(nota, "confianca", None),
            data_processamento or datetime.now().isoformat(timespec="seconds"),
        ),
    )
    nota_id = cursor.lastrowid
    conexao.executemany(
        "INSERT INTO itens (nota_id, descricao, valor) VALUES (?, ?, ?)",
        [(nota_id, _texto(i.get("descricao")), normalizar_valor(i.get("valor"))) for i in (nota.itens or [])],
    )
    return True


# ─────────────────────────────────────────────
# Leitura (usada pelo dashboard e pelas exportações)
# ─────────────────────────────────────────────

def carregar_notas(caminho_banco: str = CAMINHO_BANCO) -> pd.DataFrame:
    with sessao(caminho_banco) as conexao:
        df = pd.read_sql_query("SELECT * FROM notas ORDER BY data_emissao", conexao)
    df["data_emissao"] = pd.to_datetime(df["data_emissao"])
    return df


def carregar_itens(caminho_banco: str = CAMINHO_BANCO) -> pd.DataFrame:
    with sessao(caminho_banco) as conexao:
        df = pd.read_sql_query(
            """SELECT i.id, i.nota_id, n.numero, n.data_emissao, n.nome_emitente,
                      i.descricao, i.valor
               FROM itens i JOIN notas n ON n.id = i.nota_id
               ORDER BY n.data_emissao""",
            conexao,
        )
    df["data_emissao"] = pd.to_datetime(df["data_emissao"])
    return df


# ─────────────────────────────────────────────
# Migração do Excel da Etapa 3
# ─────────────────────────────────────────────

def migrar_excel(caminho_planilha: str, caminho_banco: str = CAMINHO_BANCO) -> dict:
    """
    Importa um notas_fiscais.xlsx existente para o banco.
    Ignora as linhas "TOTAL GERAL" e linhas vazias que a Etapa 3 deixava na aba Resumo.
    Retorna a contagem de notas importadas e ignoradas.
    """
    from types import SimpleNamespace

    resumo = pd.read_excel(caminho_planilha, sheet_name="Resumo")
    try:
        itens = pd.read_excel(caminho_planilha, sheet_name="Itens")
    except ValueError:
        itens = pd.DataFrame(columns=["Número NF", "Nome Emitente", "Descrição Item", "Valor Item (R$)"])

    resumo = resumo[resumo["Nome Emitente"].astype(str).str.strip().str.upper() != "TOTAL GERAL"]
    resumo = resumo.dropna(subset=["Número NF", "Nome Emitente", "Valor Total (R$)"], how="all")

    importadas, ignoradas = 0, 0
    with sessao(caminho_banco) as conexao:
        for _, linha in resumo.iterrows():
            numero = _texto(linha.get("Número NF"))
            itens_nota = itens[
                (itens["Número NF"].map(_texto) == numero)
                & (itens["Nome Emitente"].astype(str) == str(linha.get("Nome Emitente")))
            ]
            nota = SimpleNamespace(
                numero=numero,
                data_emissao=linha.get("Data Emissão"),
                cnpj_emitente=linha.get("CNPJ Emitente"),
                nome_emitente=linha.get("Nome Emitente"),
                valor_total=linha.get("Valor Total (R$)"),
                impostos=linha.get("Impostos (R$)"),
                itens=[
                    {"descricao": i["Descrição Item"], "valor": i["Valor Item (R$)"]}
                    for _, i in itens_nota.iterrows()
                ],
                rota="migracao_excel",
                confianca=None,
            )
            if _inserir(conexao, nota, data_processamento=_data_processamento(linha.get("Data Processamento"))):
                importadas += 1
            else:
                ignoradas += 1
    return {"importadas": importadas, "ignoradas": ignoradas}


def _data_processamento(valor) -> str | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (datetime, pd.Timestamp)):
        return valor.isoformat(timespec="seconds")
    try:
        return datetime.strptime(str(valor), "%d/%m/%Y %H:%M").isoformat(timespec="seconds")
    except ValueError:
        return None


# ─────────────────────────────────────────────
# Execução direta: migra a planilha atual
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    planilha = sys.argv[1] if len(sys.argv) > 1 else "notas_fiscais.xlsx"
    banco = sys.argv[2] if len(sys.argv) > 2 else CAMINHO_BANCO

    if not os.path.exists(planilha):
        print(f"❌ Planilha não encontrada: {planilha}")
        sys.exit(1)

    resultado = migrar_excel(planilha, banco)
    print(f"✅ Importadas: {resultado['importadas']}")
    print(f"⚠  Ignoradas : {resultado['ignoradas']} (duplicatas)")
    print(f"🗄  Banco     : {banco}")
