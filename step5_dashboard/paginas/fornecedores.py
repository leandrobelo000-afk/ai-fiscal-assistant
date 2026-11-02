import plotly.express as px
import streamlit as st

from step5_dashboard import analytics, componentes as ui

st.title("🏢 Fornecedores")

notas, _ = ui.carregar_dados()
if notas.empty:
    ui.aviso_sem_dados()
    st.stop()

filtradas = ui.filtros_sidebar(notas)
abc = analytics.curva_abc(filtradas)
if abc.empty:
    st.warning("Nenhuma nota no período e fornecedores escolhidos.")
    st.stop()

# ── Resumo da curva ABC ──────────────────────
st.subheader("Curva ABC")
st.caption("A = fornecedores que somam até 80% do gasto · B = até 95% · C = o restante")
cols = st.columns(3)
for col, classe in zip(cols, ["A", "B", "C"]):
    grupo = abc[abc["classe"] == classe]
    col.metric(f"Classe {classe}", f"{len(grupo)} fornecedor(es)",
               help=f"{grupo['participacao'].sum():.1f}% do gasto")

fig = px.bar(abc, x="fornecedor", y="participacao", color="classe",
             color_discrete_map=ui.CORES_ABC, category_orders={"classe": ["A", "B", "C"]},
             custom_data=["gasto", "acumulado"])
fig.update_traces(
    marker_cornerradius=4,
    hovertemplate="<b>%{x}</b><br>R$ %{customdata[0]:,.2f} (%{y:.1f}%)"
                  "<br>Acumulado: %{customdata[1]:.1f}%<extra></extra>",
)
fig.update_layout(xaxis_title=None, yaxis_title="% do gasto", legend_title="Classe",
                  bargap=0.3, margin=dict(t=10))
fig.update_xaxes(categoryorder="array", categoryarray=list(abc["fornecedor"]))
st.plotly_chart(fig, use_container_width=True)

# ── Tabela ───────────────────────────────────
st.dataframe(
    abc,
    hide_index=True,
    use_container_width=True,
    column_config={
        "fornecedor": "Fornecedor",
        "gasto": st.column_config.NumberColumn("Gasto (R$)", format="%.2f"),
        "qtd_notas": "Notas",
        "participacao": st.column_config.NumberColumn("% do gasto", format="%.1f%%"),
        "acumulado": st.column_config.ProgressColumn("% acumulado", format="%.1f%%",
                                                     min_value=0, max_value=100),
        "classe": "Classe",
    },
)
