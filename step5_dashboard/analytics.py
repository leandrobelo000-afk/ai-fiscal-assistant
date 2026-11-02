# ==========================================
# ETAPA 5: DASHBOARD E ANALYTICS
# ==========================================
# NOTE: This is a draft/incomplete module. The actual dashboard is implemented
# inline in step4_interface/app.py (lines ~175-233). This file is kept for
# future refactoring into a proper standalone component.

import streamlit as st
import os
from config import settings


def render_dashboard(caminho_planilha: str | None = None):
    """Render the executive dashboard. Designed to be called from app.py."""
    if caminho_planilha is None:
        caminho_planilha = settings.CAMINHO_PLANILHA

    st.divider()
    st.header("📊 Painel Executivo (Dashboard)")

    if os.path.exists(caminho_planilha):
        import pandas as pd

        df = pd.read_excel(caminho_planilha, sheet_name="Resumo")

        if not df.empty:
            faturamento_total = df["Valor Total"].sum()
            impostos_totais = df["Impostos"].sum()
            total_notas = len(df)
            ticket_medio = faturamento_total / total_notas

            def formata_br(valor):
                return f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

            kpi1, kpi2, kpi3, kpi4 = st.columns(4)

            with kpi1:
                 st.metric(label="💰 Faturamento Total", value=formata_br(faturamento_total))
            with kpi2:
                st.metric(label="🏛️ Impostos Retidos", value=formata_br(impostos_totais))
            with kpi3:
                st.metric(label="🧾 Ticket Médio", value=formata_br(ticket_medio))
            with kpi4:
                st.metric(label="📊 Total de Notas", value=total_notas)
    else:
        st.warning("Nenhuma planilha encontrada para gerar o dashboard. Por favor, faça o upload de uma nota fiscal primeiro.")