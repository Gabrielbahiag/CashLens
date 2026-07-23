from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Conta(SQLModel, table=True):
    """Uma conta ou cartão de origem das transações."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    instituicao: Optional[str] = None
    # Chave para reconhecer a mesma conta em reimportações (ex.: "banco:agencia:conta" de um OFX).
    identificador_externo: Optional[str] = Field(default=None, unique=True)


class Categoria(SQLModel, table=True):
    """Um nicho de gasto (assinaturas, alimentação, transporte...)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(unique=True)


class Regra(SQLModel, table=True):
    """Padrão de texto que, ao casar com uma transação, atribui uma categoria."""

    id: Optional[int] = Field(default=None, primary_key=True)
    padrao: str
    categoria_id: int = Field(foreign_key="categoria.id")


class Assinatura(SQLModel, table=True):
    """Uma recorrência detectada (mesmo merchant, valor e intervalo estáveis)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    merchant: str
    valor_centavos: int  # valor da cobrança mais recente observada
    periodicidade: str  # "mensal" ou "anual"
    status: str  # "ativa" ou "possivelmente_cancelada"
    primeira_cobranca: date
    ultima_cobranca: date


class Transacao(SQLModel, table=True):
    """Uma transação importada de um extrato."""

    id: str = Field(primary_key=True)
    data: date
    valor_centavos: int
    descricao_original: str
    merchant: Optional[str] = None
    categoria_id: Optional[int] = Field(default=None, foreign_key="categoria.id")
    conta_id: int = Field(foreign_key="conta.id")
    fonte: str
    assinatura_id: Optional[int] = Field(default=None, foreign_key="assinatura.id")
