from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlmodel import Session, select

from cashlens.models import Assinatura, Transacao

TOLERANCIA_VALOR_PCT = 0.10

_JANELA_MENSAL_DIAS = (25, 35)
_JANELA_ANUAL_DIAS = (350, 380)


@dataclass
class PadraoRecorrente:
    merchant: str
    periodicidade: str
    valor_centavos: int
    primeira_cobranca: date
    ultima_cobranca: date
    transacao_ids: list[str]


def _classificar_periodicidade(dias: int) -> Optional[str]:
    if _JANELA_MENSAL_DIAS[0] <= dias <= _JANELA_MENSAL_DIAS[1]:
        return "mensal"
    if _JANELA_ANUAL_DIAS[0] <= dias <= _JANELA_ANUAL_DIAS[1]:
        return "anual"
    return None


def _valores_proximos(a: int, b: int) -> bool:
    maior = max(abs(a), abs(b))
    if maior == 0:
        return True
    return abs(abs(a) - abs(b)) / maior <= TOLERANCIA_VALOR_PCT


def _agrupar_gastos_por_merchant(transacoes: list[Transacao]) -> dict[str, list[Transacao]]:
    grupos: dict[str, list[Transacao]] = defaultdict(list)
    for transacao in transacoes:
        if transacao.valor_centavos >= 0:
            continue
        chave = transacao.merchant or transacao.descricao_original
        grupos[chave].append(transacao)
    return grupos


def detectar_padroes(transacoes_do_merchant: list[Transacao]) -> list[PadraoRecorrente]:
    """Encontra cadeias de 2+ cobranças em intervalo regular (mensal/anual) e valor semelhante."""
    ordenadas = sorted(transacoes_do_merchant, key=lambda t: t.data)
    padroes = []

    i = 0
    while i < len(ordenadas) - 1:
        cadeia = [ordenadas[i]]
        periodicidade_atual = None
        j = i + 1
        while j < len(ordenadas):
            dias = (ordenadas[j].data - cadeia[-1].data).days
            periodicidade = _classificar_periodicidade(dias)
            valor_bate = _valores_proximos(cadeia[-1].valor_centavos, ordenadas[j].valor_centavos)
            periodicidade_consistente = periodicidade_atual is None or periodicidade == periodicidade_atual

            if periodicidade and valor_bate and periodicidade_consistente:
                cadeia.append(ordenadas[j])
                periodicidade_atual = periodicidade
                j += 1
            else:
                break

        if len(cadeia) >= 2:
            merchant = cadeia[0].merchant or cadeia[0].descricao_original
            padroes.append(
                PadraoRecorrente(
                    merchant=merchant,
                    periodicidade=periodicidade_atual,
                    valor_centavos=cadeia[-1].valor_centavos,
                    primeira_cobranca=cadeia[0].data,
                    ultima_cobranca=cadeia[-1].data,
                    transacao_ids=[t.id for t in cadeia],
                )
            )
            i = j
        else:
            i += 1

    return padroes


def _status(padrao: PadraoRecorrente, hoje: date) -> str:
    limite_dias = _JANELA_MENSAL_DIAS[1] if padrao.periodicidade == "mensal" else _JANELA_ANUAL_DIAS[1]
    if (hoje - padrao.ultima_cobranca).days > limite_dias:
        return "possivelmente_cancelada"
    return "ativa"


def _obter_ou_criar_assinatura(session: Session, padrao: PadraoRecorrente, hoje: date) -> Assinatura:
    assinatura = session.exec(
        select(Assinatura)
        .where(Assinatura.merchant == padrao.merchant)
        .where(Assinatura.periodicidade == padrao.periodicidade)
    ).first()

    if assinatura is None:
        assinatura = Assinatura(
            merchant=padrao.merchant,
            valor_centavos=padrao.valor_centavos,
            periodicidade=padrao.periodicidade,
            status=_status(padrao, hoje),
            primeira_cobranca=padrao.primeira_cobranca,
            ultima_cobranca=padrao.ultima_cobranca,
        )
    else:
        assinatura.valor_centavos = padrao.valor_centavos
        assinatura.ultima_cobranca = padrao.ultima_cobranca
        assinatura.status = _status(padrao, hoje)

    session.add(assinatura)
    session.commit()
    session.refresh(assinatura)
    return assinatura


def detectar_assinaturas(session: Session, hoje: Optional[date] = None) -> list[Assinatura]:
    """Reescaneia todas as transações em busca de recorrências e persiste/atualiza as Assinaturas."""
    hoje = hoje or date.today()
    transacoes = session.exec(select(Transacao)).all()
    grupos = _agrupar_gastos_por_merchant(transacoes)

    assinaturas = []
    for transacoes_do_merchant in grupos.values():
        for padrao in detectar_padroes(transacoes_do_merchant):
            assinatura = _obter_ou_criar_assinatura(session, padrao, hoje)
            for transacao in transacoes_do_merchant:
                if transacao.id in padrao.transacao_ids and transacao.assinatura_id != assinatura.id:
                    transacao.assinatura_id = assinatura.id
                    session.add(transacao)
            assinaturas.append(assinatura)

    session.commit()
    return assinaturas
