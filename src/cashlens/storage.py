from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine, select

from cashlens import models  # noqa: F401  (garante que as tabelas sejam registradas)
from cashlens.importers.base import ContaExterna, ExtratoImportado
from cashlens.models import Conta, Transacao

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "cashlens.db"


def get_engine(db_path: Path = DEFAULT_DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}")


def create_db_and_tables(db_path: Path = DEFAULT_DB_PATH) -> None:
    engine = get_engine(db_path)
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session(db_path: Path = DEFAULT_DB_PATH) -> Iterator[Session]:
    engine = get_engine(db_path)
    with Session(engine) as session:
        yield session


@dataclass
class ResultadoImportacao:
    novas: int
    duplicadas: int


def obter_ou_criar_conta(session: Session, conta_externa: ContaExterna) -> Conta:
    conta = session.exec(
        select(Conta).where(Conta.identificador_externo == conta_externa.identificador)
    ).first()
    if conta is not None:
        return conta

    conta = Conta(
        nome=conta_externa.identificador,
        instituicao=conta_externa.instituicao,
        identificador_externo=conta_externa.identificador,
    )
    session.add(conta)
    session.commit()
    session.refresh(conta)
    return conta


def importar_extrato(session: Session, extrato: ExtratoImportado) -> ResultadoImportacao:
    """Persiste um extrato já parseado, resolvendo a conta e pulando transações já importadas."""
    conta = obter_ou_criar_conta(session, extrato.conta)

    novas = 0
    duplicadas = 0
    for transacao_importada in extrato.transacoes:
        if session.get(Transacao, transacao_importada.id) is not None:
            duplicadas += 1
            continue

        session.add(
            Transacao(
                id=transacao_importada.id,
                data=transacao_importada.data,
                valor_centavos=transacao_importada.valor_centavos,
                descricao_original=transacao_importada.descricao_original,
                conta_id=conta.id,
                fonte=transacao_importada.fonte,
            )
        )
        novas += 1

    session.commit()
    return ResultadoImportacao(novas=novas, duplicadas=duplicadas)
