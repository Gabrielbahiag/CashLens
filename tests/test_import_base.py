from datetime import date

from cashlens.importers.base import gerar_id_transacao


def test_gerar_id_com_id_externo_ignora_dados_da_transacao():
    """Duas transações com o mesmo FITID geram o mesmo id, mesmo com descrições diferentes."""
    id_a = gerar_id_transacao(
        fonte="ofx",
        conta_identificador="0260:123",
        data=date(2026, 6, 5),
        valor_centavos=-1990,
        descricao="SPOTIFY*PREMIUM",
        id_externo="FIT1",
    )
    id_b = gerar_id_transacao(
        fonte="ofx",
        conta_identificador="0260:123",
        data=date(2026, 6, 5),
        valor_centavos=-1990,
        descricao="descrição diferente",
        id_externo="FIT1",
    )
    assert id_a == id_b


def test_gerar_id_sem_id_externo_usa_hash_dos_dados():
    """Sem FITID (fonte não fornece), transações com os mesmos dados colidem; dados diferentes não."""
    base = dict(
        fonte="csv",
        conta_identificador="0260:123",
        data=date(2026, 6, 5),
        valor_centavos=-1990,
        descricao="SPOTIFY*PREMIUM",
    )

    assert gerar_id_transacao(**base) == gerar_id_transacao(**base)
    assert gerar_id_transacao(**base) != gerar_id_transacao(**{**base, "valor_centavos": -2000})


def test_gerar_id_diferencia_contas():
    kwargs = dict(
        fonte="ofx",
        data=date(2026, 6, 5),
        valor_centavos=-1990,
        descricao="SPOTIFY*PREMIUM",
        id_externo="FIT1",
    )
    id_conta_a = gerar_id_transacao(conta_identificador="0260:111", **kwargs)
    id_conta_b = gerar_id_transacao(conta_identificador="0260:222", **kwargs)
    assert id_conta_a != id_conta_b
