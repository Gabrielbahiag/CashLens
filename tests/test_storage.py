from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.models import Conta, Transacao
from cashlens.storage import create_db_and_tables, get_session


def test_create_db_and_tables_cria_arquivo(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"

    create_db_and_tables(db_path)

    assert db_path.exists()


def test_transacao_round_trip(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)
        conta_id = conta.id

        transacao = Transacao(
            id="abc123",
            data=date(2026, 7, 1),
            valor_centavos=-1990,
            descricao_original="SPOTIFY*PREMIUM",
            conta_id=conta_id,
            fonte="ofx",
        )
        session.add(transacao)
        session.commit()

    with get_session(db_path) as session:
        resultado = session.exec(select(Transacao).where(Transacao.id == "abc123")).one()

        assert resultado.valor_centavos == -1990
        assert resultado.descricao_original == "SPOTIFY*PREMIUM"
        assert resultado.conta_id == conta_id
