from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.models import Assinatura, Conta, Transacao
from cashlens.recurrence import detectar_assinaturas, detectar_padroes
from cashlens.storage import create_db_and_tables, get_session


def _transacao(id_: str, dias_desde_epoca: date, valor_centavos: int, merchant: str, conta_id: int = 1) -> Transacao:
    return Transacao(
        id=id_,
        data=dias_desde_epoca,
        valor_centavos=valor_centavos,
        descricao_original=f"{merchant.upper()}*COBRANCA",
        merchant=merchant,
        conta_id=conta_id,
        fonte="ofx",
    )


def test_detectar_padroes_reconhece_cobranca_mensal_estavel():
    transacoes = [
        _transacao("t1", date(2026, 3, 5), -1990, "Spotify"),
        _transacao("t2", date(2026, 4, 5), -1990, "Spotify"),
        _transacao("t3", date(2026, 5, 6), -1990, "Spotify"),
    ]

    padroes = detectar_padroes(transacoes)

    assert len(padroes) == 1
    padrao = padroes[0]
    assert padrao.periodicidade == "mensal"
    assert padrao.valor_centavos == -1990
    assert padrao.primeira_cobranca == date(2026, 3, 5)
    assert padrao.ultima_cobranca == date(2026, 5, 6)
    assert padrao.transacao_ids == ["t1", "t2", "t3"]


def test_detectar_padroes_tolera_pequena_variacao_de_valor():
    transacoes = [
        _transacao("t1", date(2026, 3, 5), -1990, "Netflix"),
        _transacao("t2", date(2026, 4, 5), -2090, "Netflix"),  # ~5% de aumento, dentro da tolerância
    ]

    padroes = detectar_padroes(transacoes)
    assert len(padroes) == 1


def test_detectar_padroes_ignora_variacao_de_valor_grande():
    transacoes = [
        _transacao("t1", date(2026, 3, 5), -1990, "Netflix"),
        _transacao("t2", date(2026, 4, 5), -5000, "Netflix"),  # aumento grande demais
    ]

    assert detectar_padroes(transacoes) == []


def test_detectar_padroes_ignora_intervalo_irregular():
    transacoes = [
        _transacao("t1", date(2026, 3, 5), -1990, "Loja"),
        _transacao("t2", date(2026, 3, 12), -1990, "Loja"),  # uma semana depois, não é assinatura
    ]

    assert detectar_padroes(transacoes) == []


def test_detectar_padroes_uma_unica_cobranca_nao_e_recorrencia():
    transacoes = [_transacao("t1", date(2026, 3, 5), -1990, "Compra Única")]
    assert detectar_padroes(transacoes) == []


def test_detectar_padroes_reconhece_cobranca_anual():
    transacoes = [
        _transacao("t1", date(2025, 6, 1), -12000, "Amazon"),
        _transacao("t2", date(2026, 6, 3), -12000, "Amazon"),
    ]

    padroes = detectar_padroes(transacoes)
    assert len(padroes) == 1
    assert padroes[0].periodicidade == "anual"


def test_detectar_assinaturas_persiste_e_liga_transacoes(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        for id_, mes in [("t1", 3), ("t2", 4), ("t3", 5)]:
            session.add(_transacao(id_, date(2026, mes, 5), -1990, "Spotify", conta_id=conta.id))
        session.commit()

        assinaturas = detectar_assinaturas(session, hoje=date(2026, 5, 10))

        assert len(assinaturas) == 1
        assinatura = assinaturas[0]
        assert assinatura.merchant == "Spotify"
        assert assinatura.status == "ativa"

        for id_ in ("t1", "t2", "t3"):
            transacao = session.get(Transacao, id_)
            assert transacao.assinatura_id == assinatura.id


def test_detectar_assinaturas_status_possivelmente_cancelada_quando_atrasada(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        for id_, mes in [("t1", 1), ("t2", 2)]:
            session.add(_transacao(id_, date(2026, mes, 5), -1990, "Spotify", conta_id=conta.id))
        session.commit()

        # "hoje" bem depois da última cobrança esperada -> parece cancelada
        assinaturas = detectar_assinaturas(session, hoje=date(2026, 6, 20))

        assert assinaturas[0].status == "possivelmente_cancelada"


def test_detectar_assinaturas_e_idempotente(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        for id_, mes in [("t1", 3), ("t2", 4), ("t3", 5)]:
            session.add(_transacao(id_, date(2026, mes, 5), -1990, "Spotify", conta_id=conta.id))
        session.commit()

        detectar_assinaturas(session, hoje=date(2026, 5, 10))
        detectar_assinaturas(session, hoje=date(2026, 5, 10))

        todas = session.exec(select(Assinatura)).all()
        assert len(todas) == 1
