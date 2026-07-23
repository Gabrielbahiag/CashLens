from datetime import date
from pathlib import Path

from cashlens.categorize import (
    adicionar_regra,
    aplicar_categorizacao,
    carregar_regras,
    categorizar,
)
from cashlens.models import Categoria, Conta, Transacao
from cashlens.storage import create_db_and_tables, get_session

REGRAS_YAML = """
categorias:
  assinaturas:
    - spotify
    - "google.*one"
  alimentacao:
    - ifood
"""


def _regras_de_teste(tmp_path: Path):
    caminho = tmp_path / "regras.yaml"
    caminho.write_text(REGRAS_YAML, encoding="utf-8")
    return caminho


def test_carregar_regras_compila_padroes(tmp_path: Path):
    regras = carregar_regras(_regras_de_teste(tmp_path))
    categorias = {r.categoria for r in regras}
    assert categorias == {"assinaturas", "alimentacao"}


def test_carregar_regras_arquivo_inexistente_retorna_vazio(tmp_path: Path):
    assert carregar_regras(tmp_path / "nao-existe.yaml") == []


def test_categorizar_casa_por_regex_case_insensitive(tmp_path: Path):
    regras = carregar_regras(_regras_de_teste(tmp_path))
    assert categorizar("Google One 100GB", regras) == "assinaturas"
    assert categorizar("IFD*IFOOD", regras) == "alimentacao"


def test_categorizar_sem_match_retorna_none(tmp_path: Path):
    regras = carregar_regras(_regras_de_teste(tmp_path))
    assert categorizar("PADARIA DO ZE", regras) is None


def test_categorizar_primeira_regra_que_casa_vence(tmp_path: Path):
    caminho = tmp_path / "regras.yaml"
    caminho.write_text(
        """
categorias:
  a:
    - spotify
  b:
    - spotify
""",
        encoding="utf-8",
    )
    regras = carregar_regras(caminho)
    assert categorizar("Spotify", regras) == "a"


def test_adicionar_regra_cria_arquivo_e_persiste(tmp_path: Path):
    caminho = tmp_path / "regras.yaml"

    adicionar_regra("lazer", "netflix", caminho)
    regras = carregar_regras(caminho)

    assert categorizar("NETFLIX.COM", regras) == "lazer"


def test_adicionar_regra_nao_duplica_padrao_existente(tmp_path: Path):
    caminho = _regras_de_teste(tmp_path)

    adicionar_regra("assinaturas", "spotify", caminho)
    regras = carregar_regras(caminho)

    padroes_assinaturas = [r.padrao for r in regras if r.categoria == "assinaturas"]
    assert padroes_assinaturas.count("spotify") == 1


def test_aplicar_categorizacao_persiste_categoria_e_conta_nao_categorizadas(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)
    regras = carregar_regras(_regras_de_teste(tmp_path))

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
                merchant="Spotify",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.add(
            Transacao(
                id="t2",
                data=date(2026, 6, 6),
                valor_centavos=-3000,
                descricao_original="PADARIA DO ZE",
                merchant="Padaria Do Ze",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.commit()

        resultado = aplicar_categorizacao(session, regras)
        assert resultado.categorizadas == 1
        assert resultado.nao_categorizadas == 1

        t1 = session.get(Transacao, "t1")
        t2 = session.get(Transacao, "t2")
        assert t1.categoria_id is not None
        assert t2.categoria_id is None

        categoria = session.get(Categoria, t1.categoria_id)
        assert categoria.nome == "assinaturas"
