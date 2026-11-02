"""
Testes para step3_spreadsheet/writer.py (compatibilidade SQLite + Excel)
"""
import pytest
import os
import tempfile
from step3_spreadsheet.writer import (
    gravar_nota,
    ja_existe,
    criar_planilha,
    CAMINHO_PLANILHA_PADRAO,
    COLUNA_TOTAL,
)
from step2_llm.processor import NotaFiscalProcessada


class TestWriterSQLite:
    """Testes com SQLite (novo padrão)."""

    def test_gravar_nota_sqlite(self, init_test_db, nota_processada_dados):
        """Grava nota em arquivo .db"""
        db_path = init_test_db

        resultado = gravar_nota(nota_processada_dados, db_path)
        assert resultado is True

        # Verifica se arquivo foi criado
        assert os.path.exists(db_path)

    def test_ja_existe_sqlite(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        assert ja_existe("12345", init_test_db) is True
        assert ja_existe("99999", init_test_db) is False

    def test_duplicata_sqlite(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        resultado = gravar_nota(nota_processada_dados, init_test_db)
        assert resultado is False


class TestWriterExcel:
    """Testes com Excel (compatibilidade/fallback)."""

    def test_criar_planilha_excel(self, temp_excel_path):
        criar_planilha(temp_excel_path)
        assert os.path.exists(temp_excel_path)

        # Verifica estrutura
        import pandas as pd
        df = pd.read_excel(temp_excel_path, sheet_name="Resumo")
        assert list(df.columns) == [
            "Data Processamento", "Número NF", "Data Emissão", "CNPJ Emitente",
            "Nome Emitente", "Valor Total (R$)", "Impostos (R$)", "Qtd Itens"
        ]

    def test_gravar_nota_excel(self, temp_excel_path, nota_processada_dados):
        resultado = gravar_nota(nota_processada_dados, temp_excel_path)
        assert resultado is True

        # Verifica se gravou
        import pandas as pd
        df = pd.read_excel(temp_excel_path, sheet_name="Resumo")
        assert len(df) == 1
        assert df.iloc[0]["Número NF"] == "12345"

    def test_ja_existe_excel(self, temp_excel_path, nota_processada_dados):
        criar_planilha(temp_excel_path)
        gravar_nota(nota_processada_dados, temp_excel_path)
        assert ja_existe("12345", temp_excel_path) is True

    def test_duplicata_excel(self, temp_excel_path, nota_processada_dados):
        criar_planilha(temp_excel_path)
        gravar_nota(nota_processada_dados, temp_excel_path)
        resultado = gravar_nota(nota_processada_dados, temp_excel_path)
        assert resultado is False


class TestWriterAutoDetect:
    """Testes de detecção automática .db vs .xlsx."""

    def test_detecta_sqlite_por_extensao(self, init_test_db, nota_processada_dados):
        """Se termina em .db, usa SQLite."""
        db_path = init_test_db
        resultado = gravar_nota(nota_processada_dados, db_path)
        assert resultado is True
        assert os.path.exists(db_path)

    def test_detecta_excel_por_extensao(self, temp_excel_path, nota_processada_dados):
        """Se termina em .xlsx, usa Excel."""
        resultado = gravar_nota(nota_processada_dados, temp_excel_path)
        assert resultado is True
        assert os.path.exists(temp_excel_path)

    def test_caminho_padrao_do_config(self):
        """CAMINHO_PLANILHA_PADRAO vem do settings."""
        assert CAMINHO_PLANILHA_PADRAO == "notas_fiscais.xlsx"
        # Com .env customizado, seria o valor do .env


class TestWriterEstruturaDados:
    """Testes da estrutura de dados gravada."""

    def test_itens_gravados_corretamente(self, init_test_db):
        nota = NotaFiscalProcessada()
        nota.numero = "TESTE001"
        nota.data_emissao = "01/01/2024"
        nota.cnpj_emitente = "11.111.111/1111-11"
        nota.nome_emitente = "EMPRESA TESTE"
        nota.valor_total = 150.00
        nota.impostos = 15.00
        nota.itens = [
            {"descricao": "PRODUTO A", "valor": 50.00},
            {"descricao": "PRODUTO B", "valor": 100.00},
        ]
        nota.rota = "vision"
        nota.confianca = "alta"

        gravar_nota(nota, init_test_db)

        # Verifica via CRUD
        from step3_database.crud import obter_todos_itens_para_dataframe
        df_itens = obter_todos_itens_para_dataframe(init_test_db)

        assert len(df_itens) == 2
        assert df_itens.iloc[0]["descricao"] == "PRODUTO A"
        assert df_itens.iloc[0]["valor"] == 50.00
        assert df_itens.iloc[1]["descricao"] == "PRODUTO B"

    def test_nota_sem_itens(self, init_test_db):
        nota = NotaFiscalProcessada()
        nota.numero = "SEMITENS"
        nota.data_emissao = "01/01/2024"
        nota.cnpj_emitente = "11.111.111/1111-11"
        nota.nome_emitente = "EMPRESA SEM ITENS"
        nota.valor_total = 0.0
        nota.impostos = 0.0
        nota.itens = []
        nota.rota = "vision"
        nota.confianca = "alta"

        resultado = gravar_nota(nota, init_test_db)
        assert resultado is True

        from step3_database.crud import obter_todas_notas_para_dataframe
        df = obter_todas_notas_para_dataframe(init_test_db)
        assert df.iloc[0]["Qtd Itens"] == 0


class TestWriterEdgeCases:
    """Casos extremos."""

    def test_nota_com_impostos_none_virar_zero(self, init_test_db):
        nota = NotaFiscalProcessada()
        nota.numero = "IMPOSTOS_NONE"
        nota.data_emissao = "01/01/2024"
        nota.cnpj_emitente = "11.111.111/1111-11"
        nota.nome_emitente = "EMPRESA"
        nota.valor_total = 100.0
        nota.impostos = None  # None deve virar 0.0
        nota.itens = []

        gravar_nota(nota, init_test_db)

        from step3_database.crud import obter_todas_notas_para_dataframe
        df = obter_todas_notas_para_dataframe(init_test_db)
        assert df.iloc[0]["Impostos (R$)"] == 0.0

    def test_nota_com_valor_zero(self, init_test_db):
        nota = NotaFiscalProcessada()
        nota.numero = "VALOR_ZERO"
        nota.data_emissao = "01/01/2024"
        nota.cnpj_emitente = "11.111.111/1111-11"
        nota.nome_emitente = "EMPRESA"
        nota.valor_total = 0.0
        nota.impostos = 0.0
        nota.itens = []

        resultado = gravar_nota(nota, init_test_db)
        assert resultado is True


# ─────────────────────────────────────────────
# Testes específicos de comportamento Excel (do remote)
# ─────────────────────────────────────────────

from types import SimpleNamespace
from openpyxl import load_workbook
from step3_spreadsheet import writer


def _nota(numero, cnpj, valor):
    return SimpleNamespace(numero=numero, data_emissao="05/10/2026", cnpj_emitente=cnpj,
                           nome_emitente="Fornecedor", valor_total=valor, impostos=0.0,
                           itens=[{"descricao": "x", "valor": valor}])


def test_total_geral_fora_dos_dados(tmp_path):
    planilha = str(tmp_path / "n.xlsx")
    writer.gravar_nota(_nota("1", "11.111.111/0001-11", 10.0), planilha)
    writer.gravar_nota(_nota("2", "11.111.111/0001-11", 20.0), planilha)
    ws = load_workbook(planilha)["Resumo"]
    rotulos = [ws.cell(r, 5).value for r in range(2, ws.max_row + 1)]
    assert "TOTAL GERAL" not in rotulos
    assert ws.max_row == 3
    assert ws.cell(2, writer.COLUNA_TOTAL).value == "=SUM(F:F)"


def test_remove_totais_de_planilhas_antigas(tmp_path):
    planilha = str(tmp_path / "n.xlsx")
    writer.criar_planilha(planilha)
    wb = load_workbook(planilha)
    ws = wb["Resumo"]
    ws.append(["", "1", "", "", "A", 10.0, 0, 1])
    ws.append([None] * 8)
    ws.append([None, None, None, None, "TOTAL GERAL", "=SUM(F2:F2)"])
    wb.save(planilha)
    writer.gravar_nota(_nota("2", "22.222.222/0001-22", 20.0), planilha)
    ws = load_workbook(planilha)["Resumo"]
    assert [ws.cell(r, 6).value for r in range(2, ws.max_row + 1)] == [10.0, 20.0]


def test_duplicata_considera_cnpj(tmp_path):
    planilha = str(tmp_path / "n.xlsx")
    assert writer.gravar_nota(_nota("1", "11.111.111/0001-11", 10.0), planilha)
    assert not writer.gravar_nota(_nota("1", "11111111000111", 10.0), planilha)
    assert writer.gravar_nota(_nota("1", "22.222.222/0001-22", 10.0), planilha)
