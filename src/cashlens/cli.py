from pathlib import Path

import typer

from cashlens.categorize import adicionar_regra, aplicar_categorizacao, carregar_regras
from cashlens.importers.ofx import OfxImporter
from cashlens.normalize import aplicar_normalizacao
from cashlens.reports import gerar_relatorio_mensal
from cashlens.storage import create_db_and_tables, get_session, importar_extrato

app = typer.Typer(help="Cashlens: controle financeiro pessoal local-first.")


def _formatar_moeda(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    reais, resto = divmod(abs(centavos), 100)
    reais_str = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {reais_str},{resto:02d}"


@app.command()
def importar(caminho: Path):
    """Importa um extrato OFX, normaliza e categoriza o que reconhece."""
    create_db_and_tables()
    extrato = OfxImporter().parse(caminho)

    with get_session() as session:
        resultado_importacao = importar_extrato(session, extrato)
        aplicar_normalizacao(session)
        resultado_categorizacao = aplicar_categorizacao(session, carregar_regras())

    typer.echo(f"Transações novas: {resultado_importacao.novas}")
    typer.echo(f"Já importadas (puladas): {resultado_importacao.duplicadas}")
    typer.echo(f"Categorizadas automaticamente: {resultado_categorizacao.categorizadas}")
    typer.echo(f"Não categorizadas: {resultado_categorizacao.nao_categorizadas}")


@app.command()
def relatorio(ano: int, mes: int):
    """Mostra o relatório mensal por categoria."""
    create_db_and_tables()

    with get_session() as session:
        relatorio_mensal = gerar_relatorio_mensal(session, ano, mes)

    typer.echo(f"Relatório de {mes:02d}/{ano}")
    typer.echo(f"Total gasto: {_formatar_moeda(relatorio_mensal.total_centavos)}")
    typer.echo("")

    if not relatorio_mensal.por_categoria:
        typer.echo("Nenhum gasto categorizado no período.")
    for linha in relatorio_mensal.por_categoria:
        typer.echo(f"  {linha.categoria:<20} {_formatar_moeda(linha.total_centavos):>15} ({linha.percentual:5.1f}%)")

    if relatorio_mensal.nao_categorizadas_qtd:
        typer.echo("")
        typer.echo(
            f"  {relatorio_mensal.nao_categorizadas_qtd} transação(ões) não categorizada(s), "
            f"totalizando {_formatar_moeda(relatorio_mensal.nao_categorizadas_centavos)}. "
            "Use 'cashlens ensinar' para categorizá-las."
        )


@app.command()
def ensinar(padrao: str, categoria: str):
    """Ensina uma regra nova (padrão -> categoria) e recategoriza o que estava pendente."""
    create_db_and_tables()
    adicionar_regra(categoria, padrao)

    with get_session() as session:
        resultado = aplicar_categorizacao(session, carregar_regras())

    typer.echo(f"Regra adicionada: '{padrao}' -> {categoria}")
    typer.echo(f"Transações categorizadas agora: {resultado.categorizadas}")


if __name__ == "__main__":
    app()
