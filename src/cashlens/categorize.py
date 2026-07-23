import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml
from sqlmodel import Session, select

from cashlens.models import Transacao
from cashlens.storage import obter_ou_criar_categoria

DEFAULT_REGRAS_PATH = Path(__file__).resolve().parents[2] / "config" / "regras.yaml"


@dataclass
class RegraCompilada:
    categoria: str
    padrao: str
    regex: re.Pattern


def carregar_regras(caminho: Path = DEFAULT_REGRAS_PATH) -> list[RegraCompilada]:
    if not caminho.exists():
        return []

    dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    categorias = dados.get("categorias", {})

    regras = []
    for categoria, padroes in categorias.items():
        for padrao in padroes:
            regras.append(
                RegraCompilada(categoria=categoria, padrao=padrao, regex=re.compile(padrao, re.IGNORECASE))
            )
    return regras


def categorizar(texto: str, regras: list[RegraCompilada]) -> Optional[str]:
    """Retorna o nome da primeira categoria cujo padrão casa com o texto, ou None."""
    for regra in regras:
        if regra.regex.search(texto):
            return regra.categoria
    return None


def adicionar_regra(categoria: str, padrao: str, caminho: Path = DEFAULT_REGRAS_PATH) -> None:
    """Ensina uma nova regra: usuário confirma uma categoria pra um padrão não reconhecido."""
    dados = {}
    if caminho.exists():
        dados = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}

    categorias = dados.setdefault("categorias", {})
    padroes = categorias.setdefault(categoria, [])
    if padrao not in padroes:
        padroes.append(padrao)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=True), encoding="utf-8")


@dataclass
class ResultadoCategorizacao:
    categorizadas: int
    nao_categorizadas: int


def aplicar_categorizacao(session: Session, regras: list[RegraCompilada]) -> ResultadoCategorizacao:
    """Categoriza as transações ainda sem categoria, usando o merchant (ou a descrição crua)."""
    transacoes = session.exec(select(Transacao).where(Transacao.categoria_id.is_(None))).all()

    categorizadas = 0
    nao_categorizadas = 0
    for transacao in transacoes:
        texto = transacao.merchant or transacao.descricao_original
        nome_categoria = categorizar(texto, regras)
        if nome_categoria is None:
            nao_categorizadas += 1
            continue

        categoria = obter_ou_criar_categoria(session, nome_categoria)
        transacao.categoria_id = categoria.id
        session.add(transacao)
        categorizadas += 1

    session.commit()
    return ResultadoCategorizacao(categorizadas=categorizadas, nao_categorizadas=nao_categorizadas)
