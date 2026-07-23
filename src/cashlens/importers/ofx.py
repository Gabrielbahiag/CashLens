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

        conta_identificador = f"{stmt.account.bankid}:{stmt.account.acctid}"
        conta = ContaExterna(identificador=conta_identificador, instituicao=stmt.account.bankid)

        transacoes = []
        for txn in stmt.transactions:
            data = txn.dtposted.date()
            valor_centavos = int(txn.trnamt * 100)
            descricao = txn.memo or txn.name or ""

            transacoes.append(
                TransacaoImportada(
                    id=gerar_id_transacao(
                        fonte=self.fonte,
                        conta_identificador=conta_identificador,
                        data=data,
                        valor_centavos=valor_centavos,
                        descricao=descricao,
                        id_externo=txn.fitid,
                    ),
                    data=data,
                    valor_centavos=valor_centavos,
                    descricao_original=descricao,
                    fonte=self.fonte,
                )
            )

        return ExtratoImportado(conta=conta, transacoes=transacoes)
