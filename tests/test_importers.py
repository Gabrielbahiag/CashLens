from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.importers.ofx import OfxImporter
from cashlens.models import Conta, Transacao
from cashlens.storage import create_db_and_tables, get_session, importar_extrato

FIXTURE_OFX = Path(__file__).parent / "fixtures" / "exemplo.ofx"
FIXTURE_OFX_CARTAO = Path(__file__).parent / "fixtures" / "exemplo_cartao.ofx"


def test_parse_ofx_extrai_conta_e_transacoes():
    extrato = OfxImporter().parse(FIXTURE_OFX)

    assert extrato.conta.identificador == "0260:00012345-6"
    assert len(extrato.transacoes) == 3

    spotify = extrato.transacoes[0]
    assert spotify.data == date(2026, 6, 5)
    assert spotify.valor_centavos == -1990
    assert spotify.descricao_original == "SPOTIFY*PREMIUM"
    assert spotify.fonte == "ofx"


def test_parse_ofx_cartao_de_credito_sem_bankid():
    """Extratos de cartão usam CCACCTFROM (só acctid, sem bankid) - não pode quebrar."""
    extrato = OfxImporter().parse(FIXTURE_OFX_CARTAO)

    assert extrato.conta.identificador == "1234567890123456"
    assert extrato.conta.instituicao is None
    assert len(extrato.transacoes) == 2
    assert extrato.transacoes[0].valor_centavos == -1990


def test_parse_ofx_e_deterministico():
    primeira = OfxImporter().parse(FIXTURE_OFX)
    segunda = OfxImporter().parse(FIXTURE_OFX)

    assert [t.id for t in primeira.transacoes] == [t.id for t in segunda.transacoes]


def test_importar_extrato_persiste_transacoes(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = OfxImporter().parse(FIXTURE_OFX)

    with get_session(db_path) as session:
        resultado = importar_extrato(session, extrato)

        assert resultado.novas == 3
        assert resultado.duplicadas == 0
        assert len(session.exec(select(Transacao)).all()) == 3


def test_reimportar_mesmo_extrato_nao_duplica(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = OfxImporter().parse(FIXTURE_OFX)

    with get_session(db_path) as session:
        importar_extrato(session, extrato)
        resultado = importar_extrato(session, extrato)

        assert resultado.novas == 0
        assert resultado.duplicadas == 3
        assert len(session.exec(select(Transacao)).all()) == 3


def test_reimportar_usa_a_mesma_conta(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = OfxImporter().parse(FIXTURE_OFX)

    with get_session(db_path) as session:
        importar_extrato(session, extrato)
        importar_extrato(session, extrato)

        contas = session.exec(select(Conta)).all()
        assert len(contas) == 1
