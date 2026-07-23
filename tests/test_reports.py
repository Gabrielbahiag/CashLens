from datetime import date
from pathlib import Path

from cashlens.models import Assinatura, Categoria, Conta, Transacao
from cashlens.reports import evolucao_mensal, gerar_relatorio_mensal, resumo_assinaturas
from cashlens.storage import create_db_and_tables, get_session


def _preparar_mes_de_junho(session, conta_id: int) -> tuple[int, int]:
    alimentacao = Categoria(nome="alimentacao")
    assinaturas = Categoria(nome="assinaturas")
    session.add(alimentacao)
    session.add(assinaturas)
    session.commit()
    session.refresh(alimentacao)
    session.refresh(assinaturas)

    session.add(
        Transacao(
            id="t1",
            data=date(2026, 6, 5),
            valor_centavos=-1990,
            descricao_original="SPOTIFY*PREMIUM",
            categoria_id=assinaturas.id,
            conta_id=conta_id,
            fonte="ofx",
        )
    )
    session.add(
        Transacao(
            id="t2",
            data=date(2026, 6, 10),
            valor_centavos=-4000,
            descricao_original="IFD*IFOOD",
            categoria_id=alimentacao.id,
            conta_id=conta_id,
            fonte="ofx",
        )
    )
    session.add(
        Transacao(
            id="t3",
            data=date(2026, 6, 15),
            valor_centavos=-2000,
            descricao_original="LOJA DESCONHECIDA",
            conta_id=conta_id,
            fonte="ofx",
        )
    )
    session.add(
        Transacao(
            id="t4",
            data=date(2026, 6, 20),
            valor_centavos=250000,
            descricao_original="SALARIO",
            conta_id=conta_id,
            fonte="ofx",
        )
    )
    session.add(
        Transacao(
            id="t5",
            data=date(2026, 7, 1),
            valor_centavos=-1000,
            descricao_original="FORA_DO_MES",
            categoria_id=alimentacao.id,
            conta_id=conta_id,
            fonte="ofx",
        )
    )
    session.commit()

    return alimentacao.id, assinaturas.id


def test_relatorio_mensal_agrega_por_categoria_e_ignora_receitas_e_outros_meses(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        _preparar_mes_de_junho(session, conta.id)

        relatorio = gerar_relatorio_mensal(session, 2026, 6)

        assert relatorio.total_centavos == 1990 + 4000 + 2000
        assert relatorio.nao_categorizadas_centavos == 2000
        assert relatorio.nao_categorizadas_qtd == 1

        nomes_e_totais = {linha.categoria: linha.total_centavos for linha in relatorio.por_categoria}
        assert nomes_e_totais == {"assinaturas": 1990, "alimentacao": 4000}

        # maior categoria vem primeiro
        assert relatorio.por_categoria[0].categoria == "alimentacao"

        linha_alimentacao = next(linha for linha in relatorio.por_categoria if linha.categoria == "alimentacao")
        assert round(linha_alimentacao.percentual, 2) == round(4000 / 7990 * 100, 2)


def test_relatorio_mensal_sem_transacoes_nao_quebra(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        relatorio = gerar_relatorio_mensal(session, 2026, 1)

        assert relatorio.total_centavos == 0
        assert relatorio.por_categoria == []
        assert relatorio.nao_categorizadas_centavos == 0
        assert relatorio.nao_categorizadas_qtd == 0


def test_resumo_assinaturas_mostra_valor_como_gasto_positivo_e_ignora_canceladas(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        session.add(
            Assinatura(
                merchant="Netflix",
                valor_centavos=-3990,
                periodicidade="mensal",
                status="ativa",
                primeira_cobranca=date(2026, 3, 10),
                ultima_cobranca=date(2026, 5, 10),
            )
        )
        session.add(
            Assinatura(
                merchant="Academia",
                valor_centavos=-12000,
                periodicidade="anual",
                status="ativa",
                primeira_cobranca=date(2025, 1, 1),
                ultima_cobranca=date(2026, 1, 1),
            )
        )
        session.add(
            Assinatura(
                merchant="Spotify",
                valor_centavos=-1990,
                periodicidade="mensal",
                status="possivelmente_cancelada",
                primeira_cobranca=date(2025, 1, 1),
                ultima_cobranca=date(2025, 3, 1),
            )
        )
        session.commit()

        resumo = resumo_assinaturas(session)

        assert {linha.merchant for linha in resumo.assinaturas} == {"Netflix", "Academia"}
        assert all(linha.valor_centavos > 0 for linha in resumo.assinaturas)
        # 3990 (mensal) + 12000/12=1000 (anual rateada) = 4990
        assert resumo.total_mensal_centavos == 4990


def test_evolucao_mensal_cobre_os_ultimos_n_meses_em_ordem(tmp_path: Path):
    db_path = tmp_path / "cashlens.db"
    create_db_and_tables(db_path)

    with get_session(db_path) as session:
        conta = Conta(nome="Nubank")
        session.add(conta)
        session.commit()
        session.refresh(conta)

        session.add(
            Transacao(
                id="abr",
                data=date(2026, 4, 15),
                valor_centavos=-1000,
                descricao_original="X",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.add(
            Transacao(
                id="jun",
                data=date(2026, 6, 15),
                valor_centavos=-3000,
                descricao_original="X",
                conta_id=conta.id,
                fonte="ofx",
            )
        )
        session.commit()

        pontos = evolucao_mensal(session, date(2026, 6, 1), quantidade_meses=4)

        assert [(p.ano, p.mes) for p in pontos] == [(2026, 3), (2026, 4), (2026, 5), (2026, 6)]
        totais = {(p.ano, p.mes): p.total_centavos for p in pontos}
        assert totais[(2026, 3)] == 0
        assert totais[(2026, 4)] == 1000
        assert totais[(2026, 5)] == 0
        assert totais[(2026, 6)] == 3000


def test_evolucao_mensal_atravessa_virada_de_ano():
    # apenas checa a sequência de (ano, mês), sem precisar de dados no banco
    from cashlens.reports import _meses_ate

    assert _meses_ate(date(2026, 2, 1), 4) == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]
