"""
step3_database/crud.py
----------------------
Operações CRUD para o banco de dados SQLite.

Mantém a mesma API do writer.py original:
- gravar_nota(nota, caminho_arquivo=None) -> bool
"""

import os
import sys
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from .models import Base, Nota, Item


# Configuração do banco de dados
CAMINHO_BANCO_PADRAO = "notas_fiscais.db"


def get_engine(db_path: str = None):
    """Cria e retorna o engine do SQLAlchemy."""
    if db_path is None:
        db_path = CAMINHO_BANCO_PADRAO

    # Garante que o caminho é absoluto se for relativo
    if not os.path.isabs(db_path):
        # Resolve relativo ao diretório do projeto
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_path = os.path.join(project_root, db_path)

    # Cria o diretório se não existir
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    # SQLite com configurações para melhor performance
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False}  # Necessário para SQLite em multi-thread
    )
    return engine


def init_db(db_path: str = None) -> None:
    """
    Inicializa o banco de dados criando as tabelas se não existirem.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    print(f"  [INFO] Banco de dados inicializado em: {db_path or CAMINHO_BANCO_PADRAO}")


@contextmanager
def get_session(db_path: str = None):
    """
    Context manager para sessões do banco de dados.
    Garante commit/rollback automático e fechamento da sessão.
    """
    engine = get_engine(db_path)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ja_existe(numero_nf: str, db_path: str = None) -> bool:
    """
    Verifica se uma nota fiscal já existe no banco de dados.
    """
    with get_session(db_path) as session:
        nota = session.query(Nota).filter(Nota.numero == str(numero_nf)).first()
        return nota is not None


def gravar_nota(nota, db_path: str = None) -> bool:
    """
    Grava uma nota fiscal no banco de dados SQLite.

    Args:
        nota: Objeto NotaFiscalProcessada (da Etapa 2)
        db_path: Caminho do banco de dados (opcional, usa padrão se não informado)

    Returns:
        True se gravou com sucesso, False se a nota já existia (duplicata)

    Mantém a mesma assinatura e comportamento do writer.py original.
    """
    # Verifica duplicata
    if nota.numero and ja_existe(nota.numero, db_path):
        print(f"  [AVISO] NF {nota.numero} já registrada — ignorando.")
        return False

    # Inicializa o banco se não existir
    init_db(db_path)

    with get_session(db_path) as session:
        try:
            # Cria o registro principal da nota
            nova_nota = Nota(
                numero=nota.numero,
                data_emissao=nota.data_emissao,
                cnpj_emitente=nota.cnpj_emitente,
                nome_emitente=nota.nome_emitente,
                valor_total=nota.valor_total or 0.0,
                impostos=nota.impostos if nota.impostos is not None else 0.0,
                qtd_itens=len(nota.itens) if nota.itens else 0,
                data_processamento=datetime.now().strftime("%d/%m/%Y %H:%M"),
            )
            session.add(nova_nota)
            session.flush()  # Obtém o ID gerado

            # Cria os itens associados
            if nota.itens:
                for item in nota.itens:
                    novo_item = Item(
                        nota_id=nova_nota.id,
                        numero_nf=nota.numero,
                        data_emissao=nota.data_emissao,
                        nome_emitente=nota.nome_emitente,
                        descricao=item.get("descricao"),
                        valor=item.get("valor", 0.0),
                    )
                    session.add(novo_item)

            session.commit()
            print(f"  [OK] NF {nota.numero or 'sem número'} gravada com sucesso no SQLite.")
            return True

        except IntegrityError as e:
            session.rollback()
            print(f"  ⚠  NF {nota.numero} já registrada (erro de integridade) — ignorando.")
            return False
        except Exception as e:
            session.rollback()
            print(f"  [ERRO] Erro ao gravar no banco: {e}")
            raise


def listar_notas(db_path: str = None, limit: int = 100, offset: int = 0) -> List[Nota]:
    """
    Lista notas fiscais com paginação.
    """
    with get_session(db_path) as session:
        return session.query(Nota).order_by(Nota.created_at.desc()).offset(offset).limit(limit).all()


def obter_nota(numero_nf: str, db_path: str = None) -> Optional[Nota]:
    """
    Obtém uma nota fiscal específica pelo número.
    """
    with get_session(db_path) as session:
        return session.query(Nota).filter(Nota.numero == str(numero_nf)).first()


def obter_itens_da_nota(nota_id: int, db_path: str = None) -> List[Item]:
    """
    Obtém todos os itens de uma nota fiscal.
    """
    with get_session(db_path) as session:
        return session.query(Item).filter(Item.nota_id == nota_id).all()


def obter_todas_notas_para_dataframe(db_path: str = None):
    """
    Retorna todas as notas como DataFrame pandas (compatível com dashboard).
    """
    import pandas as pd

    with get_session(db_path) as session:
        notas = session.query(Nota).all()
        if not notas:
            return pd.DataFrame()

        dados = [nota.to_dict() for nota in notas]
        df = pd.DataFrame(dados)

        # Renomeia colunas para compatibilidade com o dashboard original
        df.rename(columns={
            "valor_total": "Valor Total (R$)",
            "impostos": "Impostos (R$)",
            "qtd_itens": "Qtd Itens",
            "data_emissao": "Data Emissão",
            "cnpj_emitente": "CNPJ Emitente",
            "nome_emitente": "Nome Emitente",
            "numero": "Número NF",
            "data_processamento": "Data Processamento",
        }, inplace=True)

        return df


def obter_todos_itens_para_dataframe(db_path: str = None):
    """
    Retorna todos os itens como DataFrame pandas.
    """
    import pandas as pd

    with get_session(db_path) as session:
        itens = session.query(Item).all()
        if not itens:
            return pd.DataFrame()

        dados = [item.to_dict() for item in itens]
        df = pd.DataFrame(dados)

        # Renomeia colunas para compatibilidade
        df.rename(columns={
            "numero_nf": "Número NF",
            "data_emissao": "Data Emissão",
            "nome_emitente": "Nome Emitente",
            "descricao": "Descrição Item",
            "valor": "Valor Item (R$)",
        }, inplace=True)

        return df


def migrar_excel_para_sqlite(excel_path: str, db_path: str = None) -> dict:
    """
    Migra dados de uma planilha Excel para o banco de dados SQLite.

    Args:
        excel_path: Caminho do arquivo Excel (.xlsx)
        db_path: Caminho do banco SQLite (opcional)

    Returns:
        Dicionário com estatísticas da migração
    """
    import pandas as pd

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {excel_path}")

    print(f"\n[INFO] Iniciando migração de {excel_path} para SQLite...")

    # Inicializa o banco
    init_db(db_path)

    stats = {
        "notas_migradas": 0,
        "notas_ignoradas": 0,
        "itens_migrados": 0,
        "erros": []
    }

    try:
        # Lê a aba "Resumo"
        df_resumo = pd.read_excel(excel_path, sheet_name="Resumo")

        if df_resumo.empty:
            print("  ⚠ Planilha 'Resumo' está vazia.")
            return stats

        print(f"  [INFO] Encontradas {len(df_resumo)} notas na aba 'Resumo'")

        # Lê a aba "Itens" se existir
        df_itens = None
        try:
            df_itens = pd.read_excel(excel_path, sheet_name="Itens")
            print(f"  [INFO] Encontrados {len(df_itens)} itens na aba 'Itens'")
        except Exception:
            print("  ⚠ Aba 'Itens' não encontrada ou vazia")
            df_itens = pd.DataFrame()

        # Processa cada nota
        with get_session(db_path) as session:
            for _, row in df_resumo.iterrows():
                try:
                    numero_nf = str(row.get("Número NF", "")).strip()
                    if not numero_nf or numero_nf.lower() == "nan":
                        continue

                    # Verifica se já existe
                    existente = session.query(Nota).filter(Nota.numero == numero_nf).first()
                    if existente:
                        stats["notas_ignoradas"] += 1
                        continue

                    # Cria a nota
                    nova_nota = Nota(
                        numero=numero_nf,
                        data_emissao=str(row.get("Data Emissão", "")) if pd.notna(row.get("Data Emissão")) else None,
                        cnpj_emitente=str(row.get("CNPJ Emitente", "")) if pd.notna(row.get("CNPJ Emitente")) else None,
                        nome_emitente=str(row.get("Nome Emitente", "")) if pd.notna(row.get("Nome Emitente")) else None,
                        valor_total=float(row.get("Valor Total (R$)", 0)) if pd.notna(row.get("Valor Total (R$)")) else 0.0,
                        impostos=float(row.get("Impostos (R$)", 0)) if pd.notna(row.get("Impostos (R$)")) else 0.0,
                        qtd_itens=int(row.get("Qtd Itens", 0)) if pd.notna(row.get("Qtd Itens")) else 0,
                        data_processamento=str(row.get("Data Processamento", "")) if pd.notna(row.get("Data Processamento")) else None,
                    )
                    session.add(nova_nota)
                    session.flush()

                    # Adiciona os itens desta nota
                    itens_nota = df_itens[df_itens["Número NF"] == numero_nf] if not df_itens.empty else pd.DataFrame()
                    for _, item_row in itens_nota.iterrows():
                        novo_item = Item(
                            nota_id=nova_nota.id,
                            numero_nf=numero_nf,
                            data_emissao=str(item_row.get("Data Emissão", "")) if pd.notna(item_row.get("Data Emissão")) else None,
                            nome_emitente=str(item_row.get("Nome Emitente", "")) if pd.notna(item_row.get("Nome Emitente")) else None,
                            descricao=str(item_row.get("Descrição Item", "")) if pd.notna(item_row.get("Descrição Item")) else None,
                            valor=float(item_row.get("Valor Item (R$)", 0)) if pd.notna(item_row.get("Valor Item (R$)")) else 0.0,
                        )
                        session.add(novo_item)
                        stats["itens_migrados"] += 1

                    stats["notas_migradas"] += 1

                except Exception as e:
                    stats["erros"].append(f"Nota {numero_nf}: {str(e)}")
                    print(f"  [ERRO] Erro ao migrar nota {numero_nf}: {e}")

            session.commit()

        print(f"\n[OK] Migração concluída!")
        print(f"  [OK] Notas migradas: {stats['notas_migradas']}")
        print(f"  [AVISO] Notas ignoradas (duplicatas): {stats['notas_ignoradas']}")
        print(f"  [OK] Itens migrados: {stats['itens_migrados']}")
        if stats["erros"]:
            print(f"  [ERRO] Erros: {len(stats['erros'])}")

        return stats

    except Exception as e:
        print(f"  [ERRO] Erro na migração: {e}")
        stats["erros"].append(str(e))
        return stats


def get_estatisticas(db_path: str = None) -> dict:
    """
    Retorna estatísticas gerais do banco de dados.
    """
    with get_session(db_path) as session:
        total_notas = session.query(Nota).count()
        total_itens = session.query(Item).count()

        # Soma de valores
        faturamento = session.query(func.sum(Nota.valor_total)).scalar() or 0.0
        impostos = session.query(func.sum(Nota.impostos)).scalar() or 0.0

        return {
            "total_notas": total_notas,
            "total_itens": total_itens,
            "faturamento_total": faturamento,
            "impostos_totais": impostos,
            "ticket_medio": faturamento / total_notas if total_notas > 0 else 0.0,
        }


if __name__ == "__main__":
    # Teste rápido
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from step2_llm.processor import NotaFiscalProcessada

    # Testa a criação do banco
    init_db("teste.db")

    # Testa gravação
    nota_teste = NotaFiscalProcessada(
        numero="12345",
        data_emissao="01/01/2024",
        cnpj_emitente="12.345.678/0001-90",
        nome_emitente="Empresa Teste LTDA",
        valor_total=100.50,
        impostos=15.00,
        itens=[{"descricao": "Produto A", "valor": 50.00}, {"descricao": "Produto B", "valor": 50.50}],
    )

    resultado = gravar_nota(nota_teste, "teste.db")
    print(f"Resultado: {resultado}")

    # Testa listagem
    notas = listar_notas("teste.db")
    for n in notas:
        print(n.to_dict())

    # Testa estatísticas
    stats = get_estatisticas("teste.db")
    print(f"Estatísticas: {stats}")

    # Limpa arquivo de teste
    if os.path.exists("teste.db"):
        os.remove("teste.db")
        print("Arquivo de teste removido.")