import plotly.express as px
import streamlit as st

from step5_dashboard import analytics, componentes as ui

st.title("🧺 Itens")

notas, itens = ui.carregar_dados()
if notas.empty:
    ui.aviso_sem_dados()
    st.stop()

filtradas = ui.filtros_sidebar(notas)
itens_filtrados = itens[itens["nota_id"].isin(filtradas["id"])]
if itens_filtrados.empty:
    st.warning("Nenhum item no período e fornecedores escolhidos.")
    st.stop()

st.caption("A leitura da IA traz até 5 itens principais por nota, então estes valores são parciais.")

st.subheader("Itens com maior gasto")
top = analytics.top_itens(itens_filtrados, n=15).iloc[::-1]
fig = px.bar(top, x="gasto", y="item", orientation="h", custom_data=["ocorrencias"],
             color_discrete_sequence=[ui.COR_PRINCIPAL])
fig.update_traces(
    marker_cornerradius=4,
    hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<br>Comprado %{customdata[0]}x<extra></extra>",
)
fig.update_layout(xaxis_title="R$", yaxis_title=None, margin=dict(t=10), height=80 + 28 * len(top))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Todos os itens")
busca = st.text_input("Buscar item", placeholder="ex.: arroz")
tabela = itens_filtrados
if busca:
    tabela = tabela[tabela["descricao"].fillna("").str.contains(busca, case=False, regex=False)]
st.dataframe(
    tabela[["data_emissao", "numero", "nome_emitente", "descricao", "valor"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "data_emissao": st.column_config.DateColumn("Emissão", format="DD/MM/YYYY"),
        "numero": "Nº NF",
        "nome_emitente": "Fornecedor",
        "descricao": "Item",
        "valor": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
    },
)
