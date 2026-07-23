from cashlens.formatting import (
    CORES_CATEGORICAS,
    COR_NAO_CATEGORIZADO,
    badge_categoria_html,
    cores_por_categoria,
    formatar_moeda,
)


def test_formata_valor_positivo():
    assert formatar_moeda(199000) == "R$ 1.990,00"


def test_formata_valor_negativo():
    assert formatar_moeda(-1990) == "-R$ 19,90"


def test_formata_zero():
    assert formatar_moeda(0) == "R$ 0,00"


def test_formata_valor_com_apenas_centavos():
    assert formatar_moeda(5) == "R$ 0,05"


def test_cores_por_categoria_e_deterministico():
    mapa_a = cores_por_categoria(["transporte", "alimentacao", "assinaturas"])
    mapa_b = cores_por_categoria(["assinaturas", "transporte", "alimentacao"])
    assert mapa_a == mapa_b


def test_cores_por_categoria_atribui_cores_distintas():
    mapa = cores_por_categoria(["alimentacao", "assinaturas", "transporte"])
    assert len(set(mapa.values())) == 3
    assert all(cor in CORES_CATEGORICAS for cor in mapa.values())


def test_cores_por_categoria_repete_apos_estourar_a_paleta():
    nomes = [f"categoria-{i}" for i in range(len(CORES_CATEGORICAS) + 1)]
    mapa = cores_por_categoria(nomes)
    nomes_ordenados = sorted(nomes)
    assert mapa[nomes_ordenados[0]] == mapa[nomes_ordenados[-1]]


def test_badge_categoria_usa_a_cor_do_mapa():
    mapa = {"alimentacao": "#123456"}
    badge = badge_categoria_html("alimentacao", mapa)
    assert "#123456" in badge
    assert "alimentacao" in badge


def test_badge_categoria_none_usa_cor_neutra_e_texto_padrao():
    badge = badge_categoria_html(None, {})
    assert COR_NAO_CATEGORIZADO in badge
    assert "Não categorizado" in badge


def test_badge_categoria_escapa_html():
    mapa = {"<script>": "#123456"}
    badge = badge_categoria_html("<script>", mapa)
    assert "<script>" not in badge
    assert "&lt;script&gt;" in badge
