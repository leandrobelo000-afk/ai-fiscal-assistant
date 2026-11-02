"""
step3_database/models.py
------------------------
Modelos SQLAlchemy para as tabelas do banco de dados SQLite.

Tabelas:
- notas: id, numero, data_emissao, cnpj_emitente, nome_emitente, valor_total, impostos, qtd_itens, data_processamento, created_at
- itens: id, nota_id, numero_nf, data_emissao, nome_emitente, descricao, valor
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Nota(Base):
    """
    Tabela 'notas' - Dados principais de cada nota fiscal processada.
    Corresponde à aba "Resumo" da planilha Excel original.
    """
    __tablename__ = "notas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    numero = Column(String(50), unique=True, nullable=False, index=True)
    data_emissao = Column(String(20), nullable=True)  # Formato DD/MM/AAAA
    cnpj_emitente = Column(String(30), nullable=True)
    nome_emitente = Column(String(200), nullable=True)
    valor_total = Column(Float, default=0.0, nullable=False)
    impostos = Column(Float, default=0.0, nullable=False)
    qtd_itens = Column(Integer, default=0, nullable=False)
    data_processamento = Column(String(20), nullable=True)  # Formato DD/MM/YYYY HH:MM
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relacionamento com itens
    itens = relationship("Item", back_populates="nota", cascade="all, delete-orphan")

    # Índices para consultas frequentes
    __table_args__ = (
        Index("ix_notas_data_emissao", "data_emissao"),
        Index("ix_notas_cnpj_emitente", "cnpj_emitente"),
        Index("ix_notas_data_processamento", "data_processamento"),
    )

    def __repr__(self):
        return f"<Nota(id={self.id}, numero={self.numero}, valor_total={self.valor_total})>"

    def to_dict(self):
        """Converte para dicionário compatível com a API original."""
        return {
            "id": self.id,
            "numero": self.numero,
            "data_emissao": self.data_emissao,
            "cnpj_emitente": self.cnpj_emitente,
            "nome_emitente": self.nome_emitente,
            "valor_total": self.valor_total,
            "impostos": self.impostos,
            "qtd_itens": self.qtd_itens,
            "data_processamento": self.data_processamento,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Item(Base):
    """
    Tabela 'itens' - Itens individuais de cada nota fiscal.
    Corresponde à aba "Itens" da planilha Excel original.
    """
    __tablename__ = "itens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nota_id = Column(Integer, ForeignKey("notas.id", ondelete="CASCADE"), nullable=False, index=True)
    numero_nf = Column(String(50), nullable=False, index=True)
    data_emissao = Column(String(20), nullable=True, index=True)
    nome_emitente = Column(String(200), nullable=True)
    descricao = Column(String(500), nullable=True)
    valor = Column(Float, default=0.0, nullable=False)

    # Relacionamento com a nota
    nota = relationship("Nota", back_populates="itens")

    # Índices adicionais (index=True nas colunas já cria os índices básicos)
    __table_args__ = ()

    def __repr__(self):
        return f"<Item(id={self.id}, nota_id={self.nota_id}, descricao={self.descricao[:30] if self.descricao else None}...)>"

    def to_dict(self):
        """Converte para dicionário compatível com a API original."""
        return {
            "id": self.id,
            "nota_id": self.nota_id,
            "numero_nf": self.numero_nf,
            "data_emissao": self.data_emissao,
            "nome_emitente": self.nome_emitente,
            "descricao": self.descricao,
            "valor": self.valor,
        }