import pandas as pd

from step5_dashboard import analytics


def _notas():
    return pd.DataFrame({
        "id": [1, 2, 3, 4],
        "data_emissao": pd.to_datetime(["2026-07-10", "2026-07-20", "2026-09-05", "2026-09-06"]),
        "nome_emitente": ["Posto A", "Mercado B", "Posto A", "Farmácia C"],
        "valor_total": [700.0, 200.0, 80.0, 20.0],
        "impostos": [70.0, 10.0, None, 0.0],
    })


def test_kpis():
    k = analytics.kpis(_notas())
    assert k["gasto_total"] == 1000.0
    assert k["qtd_notas"] == 4
    assert k["ticket_medio"] == 250.0
    assert k["impostos"] == 80.0
    assert k["carga_tributaria"] == 8.0


def test_kpis_vazio():
    assert analytics.kpis(_notas().iloc[0:0])["ticket_medio"] == 0.0


def test_gasto_mensal_preenche_meses_vazios():
    mensal = analytics.gasto_mensal(_notas())
    assert list(mensal["mes"].dt.month) == [7, 8, 9]
    assert list(mensal["gasto"]) == [900.0, 0.0, 100.0]
    assert analytics.variacao_ultimo_mes(mensal) is None  # agosto = 0, sem base


def test_variacao_ultimo_mes():
    mensal = analytics.gasto_mensal(_notas().iloc[[0, 2]].assign(data_emissao=pd.to_datetime(["2026-08-01", "2026-09-01"])))
    assert analytics.variacao_ultimo_mes(mensal) == -(700 - 80) / 700 * 100


def test_curva_abc():
    abc = analytics.curva_abc(_notas())
    assert list(abc["fornecedor"]) == ["Posto A", "Mercado B", "Farmácia C"]
    # Posto A = 78% (A); Mercado B cruza os 80% (78% → 98%) e fica na classe de cima (A);
    # Farmácia C começa em 98%, acima dos 95% → C
    assert list(abc["classe"]) == ["A", "A", "C"]
    assert abc["acumulado"].iloc[-1] == 100.0


def test_filtrar():
    df = analytics.filtrar(_notas(), inicio="2026-07-15", fim="2026-09-05", fornecedores=["Mercado B", "Posto A"])
    assert list(df["id"]) == [2, 3]


def test_top_itens_agrupa_descricoes():
    itens = pd.DataFrame({"id": [1, 2, 3], "descricao": ["Arroz ", "arroz", "Café"], "valor": [10.0, 5.0, 12.0]})
    top = analytics.top_itens(itens)
    assert list(top["item"]) == ["ARROZ", "CAFÉ"]
    assert list(top["ocorrencias"]) == [2, 1]
