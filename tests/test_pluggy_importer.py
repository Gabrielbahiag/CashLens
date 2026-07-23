from datetime import date
from unittest.mock import patch

import pytest

from cashlens.importers.pluggy import PluggyError, PluggyImporter


def _resposta(metodo: str, caminho: str, *, api_key=None, corpo=None, parametros=None):
    if caminho == "/auth":
        assert corpo == {"clientId": "cid", "clientSecret": "csecret", "nonExpiring": False}
        return {"apiKey": "fake-api-key"}

    if caminho == "/accounts":
        assert api_key == "fake-api-key"
        assert parametros == {"itemId": "item-1"}
        return {
            "results": [
                {"id": "conta-corrente", "name": "Conta Corrente"},
                {"id": "cartao-credito", "name": "Cartão de Crédito"},
            ]
        }

    if caminho == "/v2/transactions":
        assert api_key == "fake-api-key"
        if parametros["accountId"] == "conta-corrente":
            return {
                "results": [
                    {
                        "id": "t1",
                        "date": "2026-06-05T00:00:00.000Z",
                        "description": "SPOTIFY*PREMIUM",
                        "type": "DEBIT",
                        "amount": 19.90,
                    },
                    {
                        "id": "t2",
                        "date": "2026-06-20T00:00:00.000Z",
                        "description": "SALARIO",
                        "type": "CREDIT",
                        "amount": 2500.00,
                    },
                ],
                "next": None,
            }
        if parametros["accountId"] == "cartao-credito":
            # cartão de crédito: "amount" positivo também para compras (DEBIT) -
            # é exatamente o caso que a checagem por "type" precisa acertar.
            return {
                "results": [
                    {
                        "id": "t3",
                        "date": "2026-06-10T00:00:00.000Z",
                        "description": "IFD*IFOOD",
                        "type": "DEBIT",
                        "amount": 45.00,
                    }
                ],
                "next": None,
            }

    raise AssertionError(f"chamada inesperada: {metodo} {caminho} {parametros}")


@patch("cashlens.importers.pluggy._requisitar", side_effect=_resposta)
def test_sincronizar_mapeia_contas_e_transacoes(mock_requisitar):
    extratos = PluggyImporter(client_id="cid", client_secret="csecret").sincronizar("item-1")

    assert len(extratos) == 2
    identificadores = {e.conta.identificador for e in extratos}
    assert identificadores == {"conta-corrente", "cartao-credito"}


@patch("cashlens.importers.pluggy._requisitar", side_effect=_resposta)
def test_sinal_segue_o_campo_type_nao_o_amount_bruto(mock_requisitar):
    extratos = PluggyImporter(client_id="cid", client_secret="csecret").sincronizar("item-1")

    conta_corrente = next(e for e in extratos if e.conta.identificador == "conta-corrente")
    spotify = next(t for t in conta_corrente.transacoes if t.descricao_original == "SPOTIFY*PREMIUM")
    salario = next(t for t in conta_corrente.transacoes if t.descricao_original == "SALARIO")
    assert spotify.valor_centavos == -1990
    assert salario.valor_centavos == 250000
    assert spotify.data == date(2026, 6, 5)

    cartao = next(e for e in extratos if e.conta.identificador == "cartao-credito")
    ifood = cartao.transacoes[0]
    # "amount" era positivo (45.00) mas type=DEBIT -> tem que virar gasto (negativo).
    assert ifood.valor_centavos == -4500


@patch("cashlens.importers.pluggy._requisitar", side_effect=_resposta)
def test_autentica_uma_unica_vez_mesmo_com_multiplas_contas(mock_requisitar):
    PluggyImporter(client_id="cid", client_secret="csecret").sincronizar("item-1")

    chamadas_auth = [c for c in mock_requisitar.call_args_list if c.args[1] == "/auth"]
    assert len(chamadas_auth) == 1


def test_segue_paginacao_por_cursor_ate_next_ser_none():
    respostas = [
        {"apiKey": "fake-api-key"},
        {"results": [{"id": "conta-1", "name": "Conta"}]},
        {
            "results": [
                {"id": "t1", "date": "2026-06-01T00:00:00Z", "description": "A", "type": "DEBIT", "amount": 10.0}
            ],
            "next": "https://api.pluggy.ai/v2/transactions?accountId=conta-1&after=cursor-abc",
        },
        {
            "results": [
                {"id": "t2", "date": "2026-06-02T00:00:00Z", "description": "B", "type": "DEBIT", "amount": 20.0}
            ],
            "next": None,
        },
    ]

    with patch("cashlens.importers.pluggy._requisitar", side_effect=respostas) as mock_requisitar:
        extratos = PluggyImporter(client_id="cid", client_secret="csecret").sincronizar("item-1")

    assert len(extratos[0].transacoes) == 2
    chamadas_transacoes = [c for c in mock_requisitar.call_args_list if c.args[1] == "/v2/transactions"]
    assert len(chamadas_transacoes) == 2
    assert chamadas_transacoes[1].kwargs["parametros"]["after"] == "cursor-abc"


def test_erro_http_vira_pluggy_error():
    with patch("cashlens.importers.pluggy._requisitar", side_effect=PluggyError("Pluggy respondeu 401")):
        with pytest.raises(PluggyError):
            PluggyImporter(client_id="cid", client_secret="errada").sincronizar("item-1")
