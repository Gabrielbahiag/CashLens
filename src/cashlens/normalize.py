import re

from sqlmodel import Session, select

from cashlens.models import Transacao

_ESPACOS = re.compile(r"\s+")

# Descrições de extrato têm anatomia inconsistente entre bancos/processadoras:
# às vezes o nome do merchant vem antes do separador (ex.: "SPOTIFY*PREMIUM"),
# às vezes depois de um código de processadora (ex.: "IFD*IFOOD"). Casar por
# substring, em vez de por posição, cobre os dois casos sem regra por banco.
_ALIASES = {
    "spotify": "Spotify",
    "netflix": "Netflix",
    "ifood": "iFood",
    "rappi": "Rappi",
    "uber": "Uber",
    "amazon": "Amazon",
    "google": "Google",
    "nubank": "Nubank",
}


def limpar_merchant(descricao: str) -> str:
    texto = _ESPACOS.sub(" ", descricao).strip()
    if not texto:
        return texto

    texto_lower = texto.lower()
    for fragmento, nome_canonico in _ALIASES.items():
        if fragmento in texto_lower:
            return nome_canonico

    return texto.title()


def aplicar_normalizacao(session: Session) -> int:
    """Preenche o merchant das transações que ainda não têm um. Retorna quantas foram atualizadas."""
    transacoes = session.exec(select(Transacao).where(Transacao.merchant.is_(None))).all()
    for transacao in transacoes:
        transacao.merchant = limpar_merchant(transacao.descricao_original)
        session.add(transacao)
    session.commit()
    return len(transacoes)
