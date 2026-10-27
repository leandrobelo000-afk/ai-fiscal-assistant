from types import SimpleNamespace

import pandas as pd
from openpyxl import Workbook

from step5_dashboard import database as db


def _nota(numero="123", cnpj="12.345.678/0001-90", valor=117.14, itens=None, **extra):
    return SimpleNamespace(
        numero=numero,
        data_emissao="05/10/2026",
        cnpj_emitente=cnpj,
        nome_emitente="Mercado Exemplo",
        valor_total=valor,
        impostos=None,
        itens=itens if itens is not None else [{"descricao": "Arroz", "valor": 20.5}],
        rota="vision",
        confianca="alta",
        **extra,
    )


def test_normalizacao():
    assert db.normalizar_data("05/10/2026") == "2026-10-05"
    assert db.normalizar_data("lixo") is None
    assert db.normalizar_cnpj("12.345.678/0001-90") == "12345678000190"
    assert db.normalizar_valor("R$ 1.117,14") == 1117.14
    assert db.normalizar_valor("117.14") == 117.14


def test_mesma_nota_grava_uma_vez(tmp_path):
    banco = tmp_path / "t.db"
    assert db.salvar_nota(_nota(), banco) is True
    # mesmo CNPJ escrito de outro jeito continua sendo a mesma nota
    assert db.salvar_nota(_nota(cnpj="12345678000190"), banco) is False
    assert len(db.carregar_notas(banco)) == 1
    assert len(db.carregar_itens(banco)) == 1


def test_mesmo_numero_de_fornecedores_diferentes(tmp_path):
    banco = tmp_path / "t.db"
    assert db.salvar_nota(_nota(cnpj="11.111.111/0001-11"), banco)
    assert db.salvar_nota(_nota(cnpj="22.222.222/0001-22"), banco)
    assert len(db.carregar_notas(banco)) == 2


def test_tipos_para_o_dashboard(tmp_path):
    banco = tmp_path / "t.db"
    db.salvar_nota(_nota(valor="117,14"), banco)
    notas = db.carregar_notas(banco)
    assert notas.loc[0, "valor_total"] == 117.14
    assert notas.loc[0, "impostos"] == 0.0
    assert pd.api.types.is_datetime64_any_dtype(notas["data_emissao"])


def test_migra_excel_antigo_ignorando_totais(tmp_path):
    planilha = tmp_path / "antiga.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws.append(["Data Processamento", "Número NF", "Data Emissão", "CNPJ Emitente",
               "Nome Emitente", "Valor Total (R$)", "Impostos (R$)", "Qtd Itens"])
    ws.append(["01/10/2026 10:00", 1, "01/10/2026", "11.111.111/0001-11", "Posto A", 100.0, 0, 1])
    ws.append([None] * 8)
    ws.append([None, None, None, None, "TOTAL GERAL", "=SUM(F2:F2)"])
    ws.append(["02/10/2026 10:00", 2, "02/10/2026", "22.222.222/0001-22", "Mercado B", 50.0, 1.5, 1])
    ws.append([None, None, None, None, "TOTAL GERAL", "=SUM(F2:F5)"])
    itens = wb.create_sheet("Itens")
    itens.append(["Número NF", "Data Emissão", "Nome Emitente", "Descrição Item", "Valor Item (R$)"])
    itens.append([1, "01/10/2026", "Posto A", "Gasolina", 100.0])
    itens.append([2, "02/10/2026", "Mercado B", "Café", 50.0])
    wb.save(planilha)

    banco = tmp_path / "t.db"
    assert db.migrar_excel(planilha, banco) == {"importadas": 2, "ignoradas": 0}
    notas = db.carregar_notas(banco)
    assert notas["valor_total"].sum() == 150.0
    assert sorted(db.carregar_itens(banco)["descricao"]) == ["Café", "Gasolina"]
    # rodar de novo não duplica
    assert db.migrar_excel(planilha, banco) == {"importadas": 0, "ignoradas": 2}
