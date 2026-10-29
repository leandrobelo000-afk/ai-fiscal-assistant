"""
step5_dashboard/componentes.py
------------------------------
Peças compartilhadas pelas páginas do dashboard: carga de dados, filtros e formatação.
"""

import os

import streamlit as st

from step5_dashboard import analytics, database

COR_PRINCIPAL = "#2a78d6"                                       # azul, série única
CORES_ABC = {"A": "#184f95", "B": "#3987e5", "C": "#9ec5f4"}    # rampa do azul: escuro = mais gasto


def formatar_brl(valor: float) -> str:
    """117140.5 → 'R$ 117.140,50'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


@st.cache_data
def _ler_banco(caminho_banco: str, _versao: float):
    # _versao (data de modificação do arquivo) invalida o cache quando entra uma nota nova
    return database.carregar_notas(caminho_banco), database.carregar_itens(caminho_banco)


def carregar_dados(caminho_banco: str = database.CAMINHO_BANCO):
    caminho_banco = os.path.abspath(caminho_banco)
    versao = os.path.getmtime(caminho_banco) if os.path.exists(caminho_banco) else 0.0
    return _ler_banco(caminho_banco, versao)


def filtros_sidebar(notas):
    """Período e fornecedores na barra lateral; devolve as notas filtradas."""
    with st.sidebar:
        st.header("🔎 Filtros")
        datas = notas["data_emissao"].dropna()
        inicio = fim = None
        if not datas.empty:
            periodo = st.date_input(
                "Período de emissão",
                value=(datas.min().date(), datas.max().date()),
                format="DD/MM/YYYY",
            )
            if isinstance(periodo, tuple) and len(periodo) == 2:
                inicio, fim = periodo
        fornecedores = st.multiselect(
            "Fornecedores", sorted(notas["nome_emitente"].dropna().unique()), placeholder="Todos"
        )
    return analytics.filtrar(notas, inicio, fim, fornecedores)


def aviso_sem_dados():
    """Aviso mostrado pelas páginas enquanto a base está vazia."""
    st.info("Nenhuma nota na base ainda. Processe uma nota na página **Processar Nota** "
            "ou migre a planilha antiga com `python step5_dashboard/database.py notas_fiscais.xlsx`.")


def link_configurar_sheets():
    """Atalho para a página de configuração do Google Sheets (só existe dentro do app completo)."""
    try:
        st.page_link("paginas/google_sheets.py", label="Conectar ao Google Sheets", icon="☁️")
    except Exception:
        st.caption("Google Sheets não configurado: abra a página Google Sheets no menu.")
