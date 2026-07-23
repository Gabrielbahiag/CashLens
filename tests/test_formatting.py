from cashlens.formatting import formatar_moeda


def test_formata_valor_positivo():
    assert formatar_moeda(199000) == "R$ 1.990,00"


def test_formata_valor_negativo():
    assert formatar_moeda(-1990) == "-R$ 19,90"


def test_formata_zero():
    assert formatar_moeda(0) == "R$ 0,00"


def test_formata_valor_com_apenas_centavos():
    assert formatar_moeda(5) == "R$ 0,05"
