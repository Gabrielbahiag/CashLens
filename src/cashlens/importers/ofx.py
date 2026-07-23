from collections import defaultdict
from pathlib import Path

from ofxtools.Parser import OFXTree

from cashlens.importers.base import (
    ContaExterna,
    ExtratoImportado,
    Importer,
    TransacaoImportada,
    gerar_id_transacao,
)


class OfxImporter(Importer):
    fonte = "ofx"

    def parse(self, caminho: Path) -> ExtratoImportado:
        tree = OFXTree()
        tree.parse(caminho)
        ofx = tree.convert()
        stmt = ofx.statements[0]

        # Extratos de cartão de crédito usam CCACCTFROM, que só tem acctid (sem
        # bankid) - diferente de conta corrente/poupança (BANKACCTFROM).
        bankid = getattr(stmt.account, "bankid", None)
        acctid = stmt.account.acctid
        conta_identificador = f"{bankid}:{acctid}" if bankid else acctid
        conta = ContaExterna(identificador=conta_identificador, instituicao=bankid)

        # O FITID deveria ser único por conta (spec OFX), mas na prática alguns
        # bancos reaproveitam o mesmo FITID para transações diferentes (ex.: uma
        # cobrança e o IOF associado a ela, no mesmo dia). Sem desambiguar, a
        # segunda transação seria descartada como "duplicata" na importação.
        ocorrencias_fitid: dict[str, int] = defaultdict(int)

        transacoes = []
        for txn in stmt.transactions:
            data = txn.dtposted.date()
            valor_centavos = int(txn.trnamt * 100)
            descricao = txn.memo or txn.name or ""

            id_externo = txn.fitid
            if id_externo:
                ocorrencia = ocorrencias_fitid[id_externo]
                ocorrencias_fitid[id_externo] += 1
                if ocorrencia > 0:
                    id_externo = f"{id_externo}#{ocorrencia}"

            transacoes.append(
                TransacaoImportada(
                    id=gerar_id_transacao(
                        fonte=self.fonte,
                        conta_identificador=conta_identificador,
                        data=data,
                        valor_centavos=valor_centavos,
                        descricao=descricao,
                        id_externo=id_externo,
                    ),
                    data=data,
                    valor_centavos=valor_centavos,
                    descricao_original=descricao,
                    fonte=self.fonte,
                )
            )

        return ExtratoImportado(conta=conta, transacoes=transacoes)
