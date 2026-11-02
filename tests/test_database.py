"""
Testes para step3_database (SQLAlchemy models + CRUD)
"""
import pytest
from datetime import datetime
from step3_database.models import Nota, Item
from step3_database.crud import (
    init_db,
    get_session,
    gravar_nota,
    ja_existe,
    obter_todas_notas_para_dataframe,
    obter_todos_itens_para_dataframe,
    get_estatisticas,
    migrar_excel_para_sqlite,
)
from step2_llm.processor import NotaFiscalProcessada


class TestModels:
    """Testes dos modelos SQLAlchemy."""

    def test_nota_criacao(self, test_db_session):
        nota = Nota(
            numero="12345",
            data_emissao="15/01/2024",
            cnpj_emitente="12.345.678/0001-90",
            nome_emitente="EMPRESA LTDA",
            valor_total=196.00,
            impostos=19.60,
            qtd_itens=3,
            data_processamento=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        test_db_session.add(nota)
        test_db_session.commit()

        assert nota.id is not None
        assert nota.numero == "12345"
        assert nota.valor_total == 196.00

    def test_item_criacao_com_fk(self, test_db_session):
        nota = Nota(
            numero="12345",
            data_emissao="15/01/2024",
            cnpj_emitente="12.345.678/0001-90",
            nome_emitente="EMPRESA LTDA",
            valor_total=196.00,
            impostos=19.60,
            qtd_itens=1,
            data_processamento=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        test_db_session.add(nota)
        test_db_session.flush()

        item = Item(
            nota_id=nota.id,
            numero_nf="12345",
            data_emissao="15/01/2024",
            nome_emitente="EMPRESA LTDA",
            descricao="PRODUTO A",
            valor=51.00,
        )
        test_db_session.add(item)
        test_db_session.commit()

        assert item.id is not None
        assert item.nota_id == nota.id
        assert item.descricao == "PRODUTO A"

    def test_relacionamento_nota_itens(self, test_db_session):
        nota = Nota(
            numero="12345",
            data_emissao="15/01/2024",
            cnpj_emitente="12.345.678/0001-90",
            nome_emitente="EMPRESA LTDA",
            valor_total=196.00,
            impostos=19.60,
            qtd_itens=2,
            data_processamento=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )
        test_db_session.add(nota)
        test_db_session.flush()

        item1 = Item(nota_id=nota.id, numero_nf="12345", data_emissao="15/01/2024",
                     nome_emitente="EMPRESA LTDA", descricao="A", valor=10.0)
        item2 = Item(nota_id=nota.id, numero_nf="12345", data_emissao="15/01/2024",
                     nome_emitente="EMPRESA LTDA", descricao="B", valor=20.0)
        test_db_session.add_all([item1, item2])
        test_db_session.commit()

        # Recarrega e verifica relacionamento
        test_db_session.refresh(nota)
        assert len(nota.itens) == 2
        assert {i.descricao for i in nota.itens} == {"A", "B"}


class TestCRUD:
    """Testes das operações CRUD."""

    def test_init_db_cria_tabelas(self, init_test_db):
        from sqlalchemy import inspect
        from step3_database.crud import get_session

        with get_session(init_test_db) as session:
            inspector = inspect(session.bind)
            tables = inspector.get_table_names()
            assert "notas" in tables
            assert "itens" in tables

    def test_gravar_nota_nova(self, init_test_db, nota_processada_dados):
        resultado = gravar_nota(nota_processada_dados, init_test_db)
        assert resultado is True

    def test_gravar_nota_duplicada_retorna_false(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        resultado = gravar_nota(nota_processada_dados, init_test_db)
        assert resultado is False

    def test_ja_existe_false_para_nova(self, init_test_db):
        assert ja_existe("99999", init_test_db) is False

    def test_ja_existe_true_apos_gravar(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        assert ja_existe("12345", init_test_db) is True

    def test_obter_notas_para_dataframe(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        df = obter_todas_notas_para_dataframe(init_test_db)
        assert len(df) == 1
        assert df.iloc[0]["numero"] == "12345"
        assert df.iloc[0]["valor_total"] == 196.00

    def test_obter_itens_para_dataframe(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        df = obter_todos_itens_para_dataframe(init_test_db)
        assert len(df) == 3
        assert list(df["descricao"]) == ["PRODUTO TESTE A", "PRODUTO TESTE B", "SERVIÇO TESTE C"]

    def test_get_estatisticas(self, init_test_db, nota_processada_dados):
        gravar_nota(nota_processada_dados, init_test_db)
        stats = get_estatisticas(init_test_db)
        assert stats["total_notas"] == 1
        assert stats["faturamento_total"] == 196.00
        assert stats["impostos_totais"] == 19.60
        assert stats["ticket_medio"] == 196.00

    def test_get_estatisticas_vazio(self, init_test_db):
        stats = get_estatisticas(init_test_db)
        assert stats["total_notas"] == 0
        assert stats["faturamento_total"] == 0.0
        assert stats["impostos_totais"] == 0.0
        assert stats["ticket_medio"] == 0.0


class TestMigracaoExcel:
    """Testes de migração Excel → SQLite."""

    def test_migrar_excel_para_sqlite(self, temp_excel_path, temp_db_path):
        """Testa migração completa."""
        # Cria Excel de teste
        import pandas as pd
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws1 = wb.active
        ws1.title = "Resumo"

        headers = ["Data Processamento", "Número NF", "Data Emissão", "CNPJ Emitente",
                   "Nome Emitente", "Valor Total (R$)", "Impostos (R$)", "Qtd Itens"]
        for col, h in enumerate(headers, 1):
            c = ws1.cell(row=1, column=col, value=h)
            c.font = Font(bold=True)

        ws1.append(["01/01/2024 10:00", "11111", "01/01/2024", "11.111.111/1111-11",
                    "EMPRESA A", 100.0, 10.0, 1])
        ws1.append(["02/01/2024 10:00", "22222", "02/01/2024", "22.222.222/2222-22",
                    "EMPRESA B", 200.0, 20.0, 2])

        ws2 = wb.create_sheet("Itens")
        headers2 = ["Número NF", "Data Emissão", "Nome Emitente", "Descrição Item", "Valor Item (R$)"]
        for col, h in enumerate(headers2, 1):
            c = ws2.cell(row=1, column=col, value=h)
            c.font = Font(bold=True)

        ws2.append(["11111", "01/01/2024", "EMPRESA A", "Item A1", 100.0])
        ws2.append(["22222", "02/01/2024", "EMPRESA B", "Item B1", 150.0])
        ws2.append(["22222", "02/01/2024", "EMPRESA B", "Item B2", 50.0])

        wb.save(temp_excel_path)

        # Migra
        stats = migrar_excel_para_sqlite(temp_excel_path, init_test_db)

        assert stats["notas_migradas"] == 2
        assert stats["itens_migrados"] == 3
        assert stats["notas_ignoradas"] == 0

        # Verifica no banco
        df = obter_todas_notas_para_dataframe(init_test_db)
        assert len(df) == 2
        assert set(df["numero"].tolist()) == {"11111", "22222"}

    def test_migrar_arquivo_inexistente(self, init_test_db):
        with pytest.raises(FileNotFoundError):
            migrar_excel_para_sqlite("inexistente.xlsx", init_test_db)


class TestIntegracaoCompleta:
    """Testes de integração do fluxo completo."""

    def test_fluxo_gravar_varias_notas(self, init_test_db):
        """Grava múltiplas notas e verifica estatísticas."""
        from step2_llm.processor import NotaFiscalProcessada

        for i in range(3):
            nota = NotaFiscalProcessada()
            nota.numero = f"NF{i:05d}"
            nota.data_emissao = f"{i+1:02d}/01/2024"
            nota.cnpj_emitente = f"{i+1:02d}.{i+1:03d}.{i+1:03d}/{i+1:04d}-{i+1:02d}"
            nota.nome_emitente = f"EMPRESA {i+1}"
            nota.valor_total = float((i+1) * 100)
            nota.impostos = float((i+1) * 10)
            nota.itens = [{"descricao": f"Item {i}", "valor": float((i+1) * 100)}]
            nota.rota = "vision"
            nota.confianca = "alta"

            gravar_nota(nota, init_test_db)

        stats = get_estatisticas(init_test_db)
        assert stats["total_notas"] == 3
        assert stats["faturamento_total"] == 600.0  # 100+200+300
        assert stats["ticket_medio"] == 200.0