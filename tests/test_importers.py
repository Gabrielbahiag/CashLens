from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.importers.ofx import OfxImporter
from cashlens.models import Conta, Transacao
from cashlens.storage import create_db_and_tables, get_session, importar_extrato

FIXTURE_OFX = Path(__file__).parent / "fixtures" / "exemplo.ofx"
FIXTURE_OFX_CARTAO = Path(__file__).parent / "fixtures" / "exemplo_cartao.ofx"
FIXTURE_OFX_FITID_DUPLICADO = Path(__file__).parent / "fixtures" / "exemplo_fitid_duplicado.ofx"


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


def test_parse_ofx_com_fitid_duplicado_nao_descarta_transacao():
    """Alguns bancos reaproveitam o mesmo FITID pra transações diferentes no mesmo dia
    (ex.: uma cobrança e o IOF associado). As duas precisam ser importadas."""
    extrato = OfxImporter().parse(FIXTURE_OFX_FITID_DUPLICADO)

    assert len(extrato.transacoes) == 2
    ids = [t.id for t in extrato.transacoes]
    assert len(set(ids)) == 2  # ids distintos, mesmo com FITID igual na origem

    valores = {t.valor_centavos for t in extrato.transacoes}
    assert valores == {-402, -11507}


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


def test_importar_com_fitid_duplicado_persiste_as_duas_transacoes(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = OfxImporter().parse(FIXTURE_OFX_FITID_DUPLICADO)

    with get_session(db_path) as session:
        resultado = importar_extrato(session, extrato)
        assert resultado.novas == 2
        assert resultado.duplicadas == 0

        resultado_reimportado = importar_extrato(session, OfxImporter().parse(FIXTURE_OFX_FITID_DUPLICADO))
        assert resultado_reimportado.novas == 0
        assert resultado_reimportado.duplicadas == 2


def test_reimportar_usa_a_mesma_conta(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = OfxImporter().parse(FIXTURE_OFX)

    with get_session(db_path) as session:
        importar_extrato(session, extrato)
        importar_extrato(session, extrato)

        contas = session.exec(select(Conta)).all()
        assert len(contas) == 1
