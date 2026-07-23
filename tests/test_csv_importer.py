from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.importers.csv import CsvImporter
from cashlens.models import Transacao
from cashlens.storage import create_db_and_tables, get_session, importar_extrato

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "exemplo.csv"


def test_parse_csv_extrai_transacoes():
    extrato = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)

    assert extrato.conta.identificador == "nubank-cartao"
    assert len(extrato.transacoes) == 4

    spotify = extrato.transacoes[0]
    assert spotify.data == date(2026, 6, 5)
    assert spotify.valor_centavos == -1990
    assert spotify.descricao_original == "SPOTIFY*PREMIUM"
    assert spotify.fonte == "csv"


def test_parse_csv_e_deterministico():
    primeira = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)
    segunda = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)

    assert [t.id for t in primeira.transacoes] == [t.id for t in segunda.transacoes]


def test_parse_csv_linhas_identicas_no_mesmo_arquivo_nao_colidem():
    """Duas compras iguais na padaria no mesmo dia são transações distintas, não uma duplicata."""
    extrato = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)

    padarias = [t for t in extrato.transacoes if t.descricao_original == "PADARIA DO ZE"]
    assert len(padarias) == 2
    assert padarias[0].id != padarias[1].id


def test_conta_diferente_gera_id_diferente_para_mesma_linha():
    extrato_a = CsvImporter(conta_identificador="conta-a").parse(FIXTURE_CSV)
    extrato_b = CsvImporter(conta_identificador="conta-b").parse(FIXTURE_CSV)

    assert extrato_a.transacoes[0].id != extrato_b.transacoes[0].id


def test_importar_csv_persiste_as_quatro_transacoes(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)

    with get_session(db_path) as session:
        resultado = importar_extrato(session, extrato)

        assert resultado.novas == 4
        assert resultado.duplicadas == 0
        assert len(session.exec(select(Transacao)).all()) == 4


def test_reimportar_csv_nao_duplica(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    extrato = CsvImporter(conta_identificador="nubank-cartao").parse(FIXTURE_CSV)

    with get_session(db_path) as session:
        importar_extrato(session, extrato)
        resultado = importar_extrato(session, extrato)

        assert resultado.novas == 0
        assert resultado.duplicadas == 4
        assert len(session.exec(select(Transacao)).all()) == 4
