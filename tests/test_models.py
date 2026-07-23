from datetime import date

from cashlens.models import Categoria, Conta, Regra, Transacao


def test_conta_requer_nome():
    conta = Conta(nome="Nubank")
    assert conta.nome == "Nubank"
    assert conta.instituicao is None


def test_categoria_tem_nome():
    categoria = Categoria(nome="assinaturas")
    assert categoria.nome == "assinaturas"


def test_regra_associa_padrao_a_categoria():
    regra = Regra(padrao="spotify", categoria_id=1)
    assert regra.padrao == "spotify"
    assert regra.categoria_id == 1


def test_transacao_valor_negativo_representa_saida():
    transacao = Transacao(
        id="abc123",
        data=date(2026, 7, 1),
        valor_centavos=-1990,
        descricao_original="SPOTIFY*PREMIUM",
        conta_id=1,
        fonte="ofx",
    )
    assert transacao.valor_centavos == -1990
    assert transacao.merchant is None
    assert transacao.categoria_id is None
    assert transacao.assinatura_id is None
