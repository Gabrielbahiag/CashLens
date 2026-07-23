from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from cashlens.models import Assinatura, Categoria, Transacao


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


@dataclass
class LinhaAssinatura:
    merchant: str
    valor_centavos: int
    periodicidade: str
    status: str


@dataclass
class ResumoAssinaturas:
    total_mensal_centavos: int
    assinaturas: list[LinhaAssinatura]


def resumo_assinaturas(session: Session) -> ResumoAssinaturas:
    """Assinaturas ativas e o total mensal recorrente (anuais rateadas por 12)."""
    ativas = session.exec(select(Assinatura).where(Assinatura.status == "ativa")).all()

    total_mensal_centavos = 0
    linhas = []
    for assinatura in ativas:
        valor_gasto = -assinatura.valor_centavos
        valor_mensalizado = valor_gasto if assinatura.periodicidade == "mensal" else round(valor_gasto / 12)
        total_mensal_centavos += valor_mensalizado
        linhas.append(
            LinhaAssinatura(
                merchant=assinatura.merchant,
                valor_centavos=valor_gasto,
                periodicidade=assinatura.periodicidade,
                status=assinatura.status,
            )
        )

    linhas.sort(key=lambda linha: linha.valor_centavos, reverse=True)
    return ResumoAssinaturas(total_mensal_centavos=total_mensal_centavos, assinaturas=linhas)


@dataclass
class PontoEvolucaoMensal:
    ano: int
    mes: int
    total_centavos: int


def _meses_ate(referencia: date, quantidade_meses: int) -> list[tuple[int, int]]:
    meses = []
    ano, mes = referencia.year, referencia.month
    for i in range(quantidade_meses - 1, -1, -1):
        m = mes - i
        a = ano
        while m <= 0:
            m += 12
            a -= 1
        meses.append((a, m))
    return meses


def evolucao_mensal(session: Session, referencia: date, quantidade_meses: int = 6) -> list[PontoEvolucaoMensal]:
    """Total gasto em cada um dos últimos `quantidade_meses` meses até `referencia` (inclusive)."""
    return [
        PontoEvolucaoMensal(ano=ano, mes=mes, total_centavos=gerar_relatorio_mensal(session, ano, mes).total_centavos)
        for ano, mes in _meses_ate(referencia, quantidade_meses)
    ]


@dataclass
class LinhaTransacao:
    data: date
    merchant: str
    categoria: Optional[str]
    valor_centavos: int


def listar_transacoes_mensais(session: Session, ano: int, mes: int) -> list[LinhaTransacao]:
    """Todas as transações do mês (gastos e entradas), da mais recente pra mais antiga."""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])

    transacoes = session.exec(
        select(Transacao)
        .where(Transacao.data >= primeiro_dia)
        .where(Transacao.data <= ultimo_dia)
        .order_by(Transacao.data.desc())
    ).all()

    linhas = []
    for transacao in transacoes:
        categoria = session.get(Categoria, transacao.categoria_id) if transacao.categoria_id else None
        linhas.append(
            LinhaTransacao(
                data=transacao.data,
                merchant=transacao.merchant or transacao.descricao_original,
                categoria=categoria.nome if categoria else None,
                valor_centavos=transacao.valor_centavos,
            )
        )
    return linhas


@dataclass
class LinhaMerchant:
    merchant: str
    total_centavos: int
    quantidade: int


def top_merchants(session: Session, ano: int, mes: int, limite: int = 10) -> list[LinhaMerchant]:
    """Merchants com maior gasto total no mês (só débitos, maior primeiro)."""
    primeiro_dia = date(ano, mes, 1)
    ultimo_dia = date(ano, mes, monthrange(ano, mes)[1])

    transacoes = session.exec(
        select(Transacao)
        .where(Transacao.data >= primeiro_dia)
        .where(Transacao.data <= ultimo_dia)
        .where(Transacao.valor_centavos < 0)
    ).all()

    totais: dict[str, int] = defaultdict(int)
    quantidades: dict[str, int] = defaultdict(int)
    for transacao in transacoes:
        chave = transacao.merchant or transacao.descricao_original
        totais[chave] += -transacao.valor_centavos
        quantidades[chave] += 1

    linhas = [
        LinhaMerchant(merchant=merchant, total_centavos=total, quantidade=quantidades[merchant])
        for merchant, total in totais.items()
    ]
    linhas.sort(key=lambda linha: linha.total_centavos, reverse=True)
    return linhas[:limite]
