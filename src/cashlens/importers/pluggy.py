import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Optional

from cashlens.importers.base import ContaExterna, ExtratoImportado, TransacaoImportada, gerar_id_transacao

BASE_URL = "https://api.pluggy.ai"


class PluggyError(RuntimeError):
    """Erro ao comunicar com a API do Pluggy."""


def _requisitar(
    metodo: str,
    caminho: str,
    *,
    api_key: Optional[str] = None,
    corpo: Optional[dict] = None,
    parametros: Optional[dict] = None,
) -> dict:
    url = f"{BASE_URL}{caminho}"
    if parametros:
        query = urllib.parse.urlencode({k: v for k, v in parametros.items() if v is not None})
        url = f"{url}?{query}"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-KEY"] = api_key

    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    requisicao = urllib.request.Request(url, data=dados, headers=headers, method=metodo)

    try:
        with urllib.request.urlopen(requisicao) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")
        raise PluggyError(f"Pluggy respondeu {erro.code} em {caminho}: {detalhe}") from erro
    except urllib.error.URLError as erro:
        raise PluggyError(f"Falha ao conectar em {caminho}: {erro.reason}") from erro


class PluggyImporter:
    """Sincroniza transações via Open Finance usando a API do Pluggy.

    Diferente dos importadores de arquivo (OFX/CSV), este não implementa a
    interface `Importer` — em vez de fazer parse de um arquivo local, ele
    autentica e sincroniza pela rede a partir de um `item_id` já consentido
    pelo usuário. Ver docs/pluggy-consentimento.md para como obter esse
    item_id (fluxo de consentimento via Pluggy Connect).

    Não testado contra a API real do Pluggy (exige credenciais de uma conta
    Pluggy, que este projeto não tem) — a lógica é coberta por testes com a
    camada HTTP mockada, com base no formato de request/response documentado
    publicamente pelo SDK oficial (pluggyai/pluggy-node).
    """

    fonte = "pluggy"

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._api_key: Optional[str] = None

    def _autenticar(self) -> str:
        if self._api_key is None:
            resposta = _requisitar(
                "POST",
                "/auth",
                corpo={
                    "clientId": self.client_id,
                    "clientSecret": self.client_secret,
                    "nonExpiring": False,
                },
            )
            self._api_key = resposta["apiKey"]
        return self._api_key

    def _listar_contas(self, item_id: str) -> list[dict]:
        api_key = self._autenticar()
        resposta = _requisitar("GET", "/accounts", api_key=api_key, parametros={"itemId": item_id})
        return resposta["results"]

    def _listar_transacoes(self, account_id: str) -> list[dict]:
        api_key = self._autenticar()
        transacoes = []
        cursor = None
        while True:
            parametros = {"accountId": account_id}
            if cursor:
                parametros["after"] = cursor
            resposta = _requisitar("GET", "/v2/transactions", api_key=api_key, parametros=parametros)
            transacoes.extend(resposta["results"])

            proximo = resposta.get("next")
            if not proximo:
                break
            cursores = urllib.parse.parse_qs(urllib.parse.urlparse(proximo).query).get("after")
            if not cursores:
                break
            cursor = cursores[0]

        return transacoes

    def _mapear_transacao(self, conta_identificador: str, bruta: dict) -> TransacaoImportada:
        data = date.fromisoformat(str(bruta["date"])[:10])
        # "amount" tem o sinal invertido em contas de cartão de crédito (Pluggy
        # representa uma compra como positiva, já que aumenta o saldo devedor).
        # O campo "type" é a fonte confiável: DEBIT = saída, CREDIT = entrada.
        sinal = -1 if bruta["type"] == "DEBIT" else 1
        valor_centavos = sinal * round(abs(bruta["amount"]) * 100)
        descricao = bruta.get("description") or bruta.get("descriptionRaw") or ""

        return TransacaoImportada(
            id=gerar_id_transacao(
                fonte=self.fonte,
                conta_identificador=conta_identificador,
                data=data,
                valor_centavos=valor_centavos,
                descricao=descricao,
                id_externo=bruta["id"],
            ),
            data=data,
            valor_centavos=valor_centavos,
            descricao_original=descricao,
            fonte=self.fonte,
        )

    def sincronizar(self, item_id: str) -> list[ExtratoImportado]:
        """Busca todas as contas de um item (conexão bancária consentida) e suas transações.

        Uma conexão pode ter mais de uma conta (ex.: conta-corrente + cartão de
        crédito), por isso retorna um ExtratoImportado por conta.
        """
        extratos = []
        for conta_bruta in self._listar_contas(item_id):
            conta_identificador = conta_bruta["id"]
            conta = ContaExterna(identificador=conta_identificador, instituicao=conta_bruta.get("name"))

            transacoes_brutas = self._listar_transacoes(conta_identificador)
            transacoes = [self._mapear_transacao(conta_identificador, t) for t in transacoes_brutas]

            extratos.append(ExtratoImportado(conta=conta, transacoes=transacoes))

        return extratos
