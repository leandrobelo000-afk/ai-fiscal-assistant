import plotly.express as px
import streamlit as st

from step5_dashboard import analytics, componentes as ui, sheets_sync
from step5_dashboard.exportacao import exportar_excel

st.title("📊 Visão Geral")

notas, itens = ui.carregar_dados()
if notas.empty:
    ui.aviso_sem_dados()
    st.stop()

filtradas = ui.filtros_sidebar(notas)
itens_filtrados = itens[itens["nota_id"].isin(filtradas["id"])]

with st.sidebar:
    st.divider()
    st.download_button(
        "⬇️ Exportar Excel (filtro atual)",
        data=exportar_excel(filtradas, itens_filtrados),
        file_name="notas_fiscais.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    if sheets_sync.configurado():
        if st.button("🔄 Sincronizar com Google Sheets", use_container_width=True):
            try:
                with st.spinner("Enviando para o Google Sheets..."):
                    enviados = sheets_sync.sincronizar()
                st.success(f"Planilha atualizada: {enviados['Notas']} nota(s), {enviados['Itens']} item(ns).")
            except Exception as e:
                st.error(sheets_sync.mensagem_amigavel(e))
        st.link_button("Abrir planilha no Google", sheets_sync.link_planilha(sheets_sync.configuracao()["sheet_id"]),
                       use_container_width=True)
    else:
        ui.link_configurar_sheets()

if filtradas.empty:
    st.warning("Nenhuma nota no período e fornecedores escolhidos.")
    st.stop()

# ── Indicadores ──────────────────────────────
k = analytics.kpis(filtradas)
mensal = analytics.gasto_mensal(filtradas)
variacao = analytics.variacao_ultimo_mes(mensal)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Gasto total", ui.formatar_brl(k["gasto_total"]),
          delta=f"{variacao:+.1f}% no último mês" if variacao is not None else None,
          delta_color="inverse")
c2.metric("Notas", k["qtd_notas"])
c3.metric("Ticket médio", ui.formatar_brl(k["ticket_medio"]))
c4.metric("Impostos", ui.formatar_brl(k["impostos"]), help="Soma dos tributos informados nas notas")
st.caption(f"Carga tributária média: {k['carga_tributaria']:.1f}% do valor das notas")

# ── Evolução mensal ──────────────────────────
st.subheader("Gasto por mês")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
mensal["rotulo"] = [f"{MESES[m.month - 1]}/{m:%y}" for m in mensal["mes"]]
fig = px.bar(mensal, x="rotulo", y="gasto", custom_data=["qtd_notas", "impostos"],
             color_discrete_sequence=[ui.COR_PRINCIPAL])
fig.update_traces(
    marker_cornerradius=4,
    hovertemplate="<b>%{x}</b><br>Gasto: R$ %{y:,.2f}<br>Notas: %{customdata[0]}"
                  "<br>Impostos: R$ %{customdata[1]:,.2f}<extra></extra>",
)
fig.update_layout(xaxis_title=None, yaxis_title="R$", bargap=0.35, margin=dict(t=10))
st.plotly_chart(fig, use_container_width=True)

# ── Fornecedores ─────────────────────────────
st.subheader("Maiores fornecedores")
top = analytics.gasto_por_fornecedor(filtradas).head(10).iloc[::-1]
fig = px.bar(top, x="gasto", y="fornecedor", orientation="h", custom_data=["qtd_notas"],
             color_discrete_sequence=[ui.COR_PRINCIPAL])
fig.update_traces(
    marker_cornerradius=4,
    hovertemplate="<b>%{y}</b><br>Gasto: R$ %{x:,.2f}<br>Notas: %{customdata[0]}<extra></extra>",
)
fig.update_layout(xaxis_title="R$", yaxis_title=None, margin=dict(t=10), height=80 + 32 * len(top))
st.plotly_chart(fig, use_container_width=True)
