import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from cashlens.categorize import adicionar_regra, aplicar_categorizacao, carregar_regras
from cashlens.formatting import formatar_moeda
from cashlens.importers.base import Importer
from cashlens.importers.csv import CsvImporter
from cashlens.importers.ofx import OfxImporter
from cashlens.importers.pluggy import PluggyError, PluggyImporter
from cashlens.normalize import aplicar_normalizacao
from cashlens.recurrence import detectar_assinaturas
from cashlens.reports import gerar_relatorio_mensal, resumo_assinaturas
from cashlens.storage import create_db_and_tables, get_session, importar_extrato

load_dotenv()

app = typer.Typer(help="Cashlens: controle financeiro pessoal local-first.")


@app.command()
def importar(
    caminho: Path,
    formato: str = typer.Option("ofx", help="Formato do arquivo: 'ofx' ou 'csv'."),
    conta: Optional[str] = typer.Option(None, help="Identificador da conta (obrigatório para 'csv')."),
):
    """Importa um extrato, normaliza, categoriza o que reconhece e reescaneia assinaturas."""
    create_db_and_tables()

    importer: Importer
    if formato == "ofx":
        importer = OfxImporter()
    elif formato == "csv":
        if not conta:
            typer.echo("Para importar CSV, informe --conta.")
            raise typer.Exit(code=1)
        importer = CsvImporter(conta_identificador=conta)
    else:
        typer.echo(f"Formato não suportado: {formato!r}. Use 'ofx' ou 'csv'.")
        raise typer.Exit(code=1)

    extrato = importer.parse(caminho)

    with get_session() as session:
        resultado_importacao = importar_extrato(session, extrato)
        aplicar_normalizacao(session)
        resultado_categorizacao = aplicar_categorizacao(session, carregar_regras())
        assinaturas = detectar_assinaturas(session)

    typer.echo(f"Transações novas: {resultado_importacao.novas}")
    typer.echo(f"Já importadas (puladas): {resultado_importacao.duplicadas}")
    typer.echo(f"Categorizadas automaticamente: {resultado_categorizacao.categorizadas}")
    typer.echo(f"Não categorizadas: {resultado_categorizacao.nao_categorizadas}")
    typer.echo(f"Assinaturas detectadas: {len(assinaturas)}")


@app.command()
def relatorio(ano: int, mes: int):
    """Mostra o relatório mensal por categoria."""
    create_db_and_tables()

    with get_session() as session:
        relatorio_mensal = gerar_relatorio_mensal(session, ano, mes)

    typer.echo(f"Relatório de {mes:02d}/{ano}")
    typer.echo(f"Total gasto: {formatar_moeda(relatorio_mensal.total_centavos)}")
    typer.echo("")

    if not relatorio_mensal.por_categoria:
        typer.echo("Nenhum gasto categorizado no período.")
    for linha in relatorio_mensal.por_categoria:
        typer.echo(f"  {linha.categoria:<20} {formatar_moeda(linha.total_centavos):>15} ({linha.percentual:5.1f}%)")

    if relatorio_mensal.nao_categorizadas_qtd:
        typer.echo("")
        typer.echo(
            f"  {relatorio_mensal.nao_categorizadas_qtd} transação(ões) não categorizada(s), "
            f"totalizando {formatar_moeda(relatorio_mensal.nao_categorizadas_centavos)}. "
            "Use 'cashlens ensinar' para categorizá-las."
        )

    with get_session() as session:
        assinaturas = resumo_assinaturas(session)

    typer.echo("")
    typer.echo(f"Assinaturas ativas — total mensal recorrente: {formatar_moeda(assinaturas.total_mensal_centavos)}")
    for linha in assinaturas.assinaturas:
        typer.echo(f"  {linha.merchant:<20} {formatar_moeda(linha.valor_centavos):>15}  ({linha.periodicidade})")


@app.command()
def ensinar(padrao: str, categoria: str):
    """Ensina uma regra nova (padrão -> categoria) e recategoriza o que estava pendente."""
    create_db_and_tables()
    adicionar_regra(categoria, padrao)

    with get_session() as session:
        resultado = aplicar_categorizacao(session, carregar_regras())

    typer.echo(f"Regra adicionada: '{padrao}' -> {categoria}")
    typer.echo(f"Transações categorizadas agora: {resultado.categorizadas}")


@app.command()
def pluggy_sincronizar(item_id: str):
    """Sincroniza transações via Open Finance (Pluggy) para uma conexão já consentida.

    Requer PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET no ambiente (.env).
    Veja docs/pluggy-consentimento.md para como obter o item_id.
    """
    client_id = os.environ.get("PLUGGY_CLIENT_ID")
    client_secret = os.environ.get("PLUGGY_CLIENT_SECRET")
    if not client_id or not client_secret:
        typer.echo("Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET (.env). Veja docs/pluggy-consentimento.md.")
        raise typer.Exit(code=1)

    create_db_and_tables()

    try:
        extratos = PluggyImporter(client_id=client_id, client_secret=client_secret).sincronizar(item_id)
    except PluggyError as erro:
        typer.echo(f"Erro ao sincronizar com o Pluggy: {erro}")
        raise typer.Exit(code=1)

    total_novas = 0
    total_duplicadas = 0
    with get_session() as session:
        for extrato in extratos:
            resultado = importar_extrato(session, extrato)
            total_novas += resultado.novas
            total_duplicadas += resultado.duplicadas
        aplicar_normalizacao(session)
        resultado_categorizacao = aplicar_categorizacao(session, carregar_regras())
        assinaturas = detectar_assinaturas(session)

    typer.echo(f"Contas sincronizadas: {len(extratos)}")
    typer.echo(f"Transações novas: {total_novas}")
    typer.echo(f"Já importadas (puladas): {total_duplicadas}")
    typer.echo(f"Categorizadas automaticamente: {resultado_categorizacao.categorizadas}")
    typer.echo(f"Não categorizadas: {resultado_categorizacao.nao_categorizadas}")
    typer.echo(f"Assinaturas detectadas: {len(assinaturas)}")


if __name__ == "__main__":
    app()
