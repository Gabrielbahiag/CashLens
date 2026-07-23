from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from cashlens.models import Categoria, Transacao


@dataclass
class LinhaCategoria:
    categoria: str
    total_centavos: int
    percentual: float


@dataclass
class RelatorioMensal:
    ano: int
    mes: int
    total_centavos: int
    por_categoria: list[LinhaCategoria]
    nao_categorizadas_centavos: int
    nao_categorizadas_qtd: int


def gerar_relatorio_mensal(session: Session, ano: int, mes: int) -> RelatorioMensal:
    """Agrega os gastos (valor negativo) do mês por categoria."""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])

    transacoes = session.exec(
        select(Transacao)
        .where(Transacao.data >= primeiro_dia)
        .where(Transacao.data <= ultimo_dia)
        .where(Transacao.valor_centavos < 0)
    ).all()

    totais_por_categoria_id: dict[int | None, int] = defaultdict(int)
    contagem_nao_categorizadas = 0
    for transacao in transacoes:
        totais_por_categoria_id[transacao.categoria_id] += -transacao.valor_centavos
        if transacao.categoria_id is None:
            contagem_nao_categorizadas += 1

    total_centavos = sum(totais_por_categoria_id.values())
    nao_categorizadas_centavos = totais_por_categoria_id.pop(None, 0)

    por_categoria = []
    for categoria_id, total in totais_por_categoria_id.items():
        categoria = session.get(Categoria, categoria_id)
        percentual = (total / total_centavos * 100) if total_centavos else 0.0
        por_categoria.append(LinhaCategoria(categoria=categoria.nome, total_centavos=total, percentual=percentual))

    por_categoria.sort(key=lambda linha: linha.total_centavos, reverse=True)

    return RelatorioMensal(
        ano=ano,
        mes=mes,
        total_centavos=total_centavos,
        por_categoria=por_categoria,
        nao_categorizadas_centavos=nao_categorizadas_centavos,
        nao_categorizadas_qtd=contagem_nao_categorizadas,
    )
