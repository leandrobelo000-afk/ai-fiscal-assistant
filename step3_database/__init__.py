"""
step3_database
--------------
Módulo de persistência usando SQLite + SQLAlchemy.
Substitui o armazenamento baseado em Excel (openpyxl) por um banco de dados relacional.

Tabelas:
- notas: dados principais da nota fiscal (resumo)
- itens: itens individuais de cada nota fiscal

API pública:
- gravar_nota(nota, db_path=None) -> bool: Mesma assinatura do writer.py original
- init_db(db_path=None): Inicializa o banco de dados
- migrar_excel_para_sqlite(excel_path, db_path): Migra dados do Excel para SQLite
"""
from .models import Nota, Item, Base
from .crud import (
    gravar_nota,
    init_db,
    get_session,
    migrar_excel_para_sqlite,
    get_estatisticas,
    obter_todas_notas_para_dataframe,
    obter_todos_itens_para_dataframe,
    ja_existe,
)

__all__ = [
    "Nota",
    "Item",
    "Base",
    "gravar_nota",
    "init_db",
    "get_session",
    "migrar_excel_para_sqlite",
    "get_estatisticas",
    "obter_todas_notas_para_dataframe",
    "obter_todos_itens_para_dataframe",
    "ja_existe",
]