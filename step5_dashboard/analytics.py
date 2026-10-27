"""
step5_dashboard/analytics.py
----------------------------
Cálculos financeiros do dashboard, separados da interface para poderem ser testados.

Todas as funções recebem os DataFrames de database.carregar_notas() / carregar_itens().
"""

import pandas as pd


# ─────────────────────────────────────────────
# Filtros
# ─────────────────────────────────────────────

def filtrar(notas: pd.DataFrame, inicio=None, fim=None, fornecedores=None) -> pd.DataFrame:
    """Filtra por período de emissão (inclusivo) e por lista de fornecedores."""
    df = notas
    if inicio is not None:
        df = df[df["data_emissao"] >= pd.Timestamp(inicio)]
    if fim is not None:
        df = df[df["data_emissao"] <= pd.Timestamp(fim)]
    if fornecedores:
        df = df[df["nome_emitente"].isin(fornecedores)]
    return df


# ─────────────────────────────────────────────
# Indicadores
# ─────────────────────────────────────────────

def kpis(notas: pd.DataFrame) -> dict:
    """Gasto total, nº de notas, ticket médio, impostos e carga tributária (%)."""
    gasto = float(notas["valor_total"].fillna(0).sum())
    impostos = float(notas["impostos"].fillna(0).sum())
    qtd = int(len(notas))
    return {
        "gasto_total": gasto,
        "qtd_notas": qtd,
        "ticket_medio": gasto / qtd if qtd else 0.0,
        "impostos": impostos,
        "carga_tributaria": impostos / gasto * 100 if gasto else 0.0,
    }


def gasto_mensal(notas: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por mês (inclusive meses sem notas), com gasto, impostos e nº de notas."""
    df = notas.dropna(subset=["data_emissao"])
    if df.empty:
        return pd.DataFrame(columns=["mes", "gasto", "impostos", "qtd_notas"])
    mensal = (
        df.groupby(df["data_emissao"].dt.to_period("M"))
        .agg(gasto=("valor_total", "sum"), impostos=("impostos", "sum"), qtd_notas=("id", "count"))
    )
    meses = pd.period_range(mensal.index.min(), mensal.index.max(), freq="M")
    mensal = mensal.reindex(meses, fill_value=0)
    mensal.index = mensal.index.to_timestamp()
    return mensal.rename_axis("mes").reset_index()


def variacao_ultimo_mes(mensal: pd.DataFrame) -> float | None:
    """Variação % do gasto do último mês contra o anterior; None se não houver base."""
    if len(mensal) < 2 or mensal["gasto"].iloc[-2] == 0:
        return None
    anterior, atual = mensal["gasto"].iloc[-2], mensal["gasto"].iloc[-1]
    return (atual - anterior) / anterior * 100


def gasto_por_fornecedor(notas: pd.DataFrame) -> pd.DataFrame:
    """Gasto e nº de notas por fornecedor, do maior para o menor."""
    return (
        notas.groupby("nome_emitente", dropna=False)
        .agg(gasto=("valor_total", "sum"), qtd_notas=("id", "count"))
        .sort_values("gasto", ascending=False)
        .reset_index()
        .rename(columns={"nome_emitente": "fornecedor"})
    )


def curva_abc(notas: pd.DataFrame, limite_a: float = 80.0, limite_b: float = 95.0) -> pd.DataFrame:
    """
    Classifica fornecedores pela participação acumulada no gasto (Pareto):
      A = até 80% do gasto, B = até 95%, C = o restante.
    O fornecedor que cruza o limite fica na classe de cima.
    """
    df = gasto_por_fornecedor(notas)
    total = df["gasto"].sum()
    if df.empty or total == 0:
        return df.assign(participacao=[], acumulado=[], classe=[])
    df["participacao"] = df["gasto"] / total * 100
    df["acumulado"] = df["participacao"].cumsum()
    acumulado_anterior = df["acumulado"] - df["participacao"]
    df["classe"] = "C"
    df.loc[acumulado_anterior < limite_b, "classe"] = "B"
    df.loc[acumulado_anterior < limite_a, "classe"] = "A"
    return df


def top_itens(itens: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Itens com maior gasto somado, agrupando descrições iguais (sem diferenciar maiúsculas)."""
    if itens.empty:
        return pd.DataFrame(columns=["item", "gasto", "ocorrencias"])
    chave = itens["descricao"].fillna("(sem descrição)").str.strip().str.upper()
    return (
        itens.assign(item=chave)
        .groupby("item")
        .agg(gasto=("valor", "sum"), ocorrencias=("id", "count"))
        .sort_values("gasto", ascending=False)
        .head(n)
        .reset_index()
    )
