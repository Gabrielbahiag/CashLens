from datetime import date
from pathlib import Path

from sqlmodel import select

from cashlens.models import Conta, Transacao
from cashlens.normalize import aplicar_normalizacao, limpar_merchant
from cashlens.storage import create_db_and_tables, get_session


def test_merchant_com_codigo_de_processadora_antes():
    assert limpar_merchant("IFD*IFOOD") == "iFood"


def test_merchant_com_nome_antes_do_separador():
    assert limpar_merchant("SPOTIFY*PREMIUM") == "Spotify"


def test_alias_e_case_insensitive():
    assert limpar_merchant("spotify premium") == "Spotify"


def test_colapsa_espacos_extras():
    assert limpar_merchant("UBER   *TRIP  SP") == "Uber"


def test_sem_alias_conhecido_aplica_title_case():
    assert limpar_merchant("  TED   RECEBIDA  ") == "Ted Recebida"


def test_string_vazia_permanece_vazia():
    assert limpar_merchant("") == ""
    assert limpar_merchant("   ") == ""


def test_aplicar_normalizacao_preenche_apenas_merchant_vazio(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        session.add(
            Transacao(
                id="t1",
                data=date(2026, 6, 5),
                valor_centavos=-1990,
                descricao_original="SPOTIFY*PREMIUM",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.add(
            Transacao(
                id="t2",
                data=date(2026, 6, 6),
                valor_centavos=-500,
                descricao_original="MERCADO XYZ",
                merchant="Já Normalizado",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.commit()

        atualizadas = aplicar_normalizacao(session)
        assert atualizadas == 1

        t1 = session.get(Transacao, "t1")
        t2 = session.get(Transacao, "t2")
        assert t1.merchant == "Spotify"
        assert t2.merchant == "Já Normalizado"
