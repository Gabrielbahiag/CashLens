import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional


@dataclass
class ContaExterna:
    """Identificação de conta como ela aparece na fonte importada (ex.: banco+número de um OFX)."""

    identificador: str
    instituicao: Optional[str] = None


@dataclass
class TransacaoImportada:
    id: str
    data: date
    valor_centavos: int
    descricao_original: str
    fonte: str


@dataclass
class ExtratoImportado:
    conta: ContaExterna
    transacoes: list[TransacaoImportada]


class Importer(ABC):
    """Interface comum a todo adaptador de importação (OFX, CSV, Open Finance...)."""

    fonte: str

    @abstractmethod
    def parse(self, caminho: Path) -> ExtratoImportado: ...


def gerar_id_transacao(
    fonte: str,
    conta_identificador: str,
    data: date,
    valor_centavos: int,
    descricao: str,
    id_externo: Optional[str] = None,
) -> str:
    """Id determinístico usado para dedup: reimportar o mesmo extrato gera os mesmos ids.

    Prioriza o id atribuído pela fonte (ex.: FITID do OFX), que já é único por conta.
    Sem id de fonte, cai para um hash dos dados da transação.
    """
    if id_externo:
        chave = f"{fonte}:{conta_identificador}:{id_externo}"
    else:
        chave = f"{fonte}:{conta_identificador}:{data.isoformat()}:{valor_centavos}:{descricao}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()
