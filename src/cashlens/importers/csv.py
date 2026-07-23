import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from cashlens.importers.base import (
    ContaExterna,
    ExtratoImportado,
    Importer,
    TransacaoImportada,
    gerar_id_transacao,
)

_FORMATOS_DATA = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y")


def _parsear_data(texto: str) -> date:
    texto = texto.strip()
    for formato in _FORMATOS_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data em formato não reconhecido: {texto!r}")


def _parsear_valor_centavos(texto: str) -> int:
    texto = texto.strip().replace("R$", "").strip()
    negativo = texto.startswith("-")
    texto = texto.lstrip("-").strip()

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    centavos = round(float(texto) * 100)
    return -centavos if negativo else centavos


class CsvImporter(Importer):
    """Importa extratos CSV genéricos com colunas 'data', 'descricao' e 'valor'.

    Diferente do OFX, um CSV não traz um id de transação estável nem os dados
    da conta — por isso a conta precisa ser informada explicitamente.
    """

    fonte = "csv"

    def __init__(self, conta_identificador: str):
        self.conta_identificador = conta_identificador

    def parse(self, caminho: Path) -> ExtratoImportado:
        with open(caminho, encoding="utf-8-sig", newline="") as arquivo:
            amostra = arquivo.read(4096)
            arquivo.seek(0)
            try:
                dialeto = csv.Sniffer().sniff(amostra, delimiters=",;")
            except csv.Error:
                dialeto = csv.excel

            leitor = csv.DictReader(arquivo, dialect=dialeto)
            colunas = {(c or "").strip().lower(): c for c in leitor.fieldnames or []}
            coluna_data = colunas.get("data")
            coluna_descricao = colunas.get("descricao") or colunas.get("descrição")
            coluna_valor = colunas.get("valor")
            if not (coluna_data and coluna_descricao and coluna_valor):
                raise ValueError("CSV precisa ter as colunas 'data', 'descricao' e 'valor'.")

            # Sem um id de origem, transações idênticas (mesma data/valor/descrição)
            # no mesmo arquivo colidiriam no hash de dedup; a ocorrência desambigua.
            ocorrencias: dict[tuple, int] = defaultdict(int)
            transacoes = []
            for linha in leitor:
                data = _parsear_data(linha[coluna_data])
                valor_centavos = _parsear_valor_centavos(linha[coluna_valor])
                descricao = linha[coluna_descricao].strip()

                chave = (data, valor_centavos, descricao)
                ocorrencia = ocorrencias[chave]
                ocorrencias[chave] += 1
                descricao_para_id = descricao if ocorrencia == 0 else f"{descricao}#{ocorrencia}"

                transacoes.append(
                    TransacaoImportada(
                        id=gerar_id_transacao(
                            fonte=self.fonte,
                            conta_identificador=self.conta_identificador,
                            data=data,
                            valor_centavos=valor_centavos,
                            descricao=descricao_para_id,
                        ),
                        data=data,
                        valor_centavos=valor_centavos,
                        descricao_original=descricao,
                        fonte=self.fonte,
                    )
                )

        conta = ContaExterna(identificador=self.conta_identificador)
        return ExtratoImportado(conta=conta, transacoes=transacoes)
