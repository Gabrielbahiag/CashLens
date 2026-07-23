import calendar
from datetime import date
from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from cashlens.formatting import badge_categoria_html, cores_por_categoria, formatar_moeda
from cashlens.reports import (
    evolucao_mensal,
    gerar_relatorio_mensal,
    listar_transacoes_mensais,
    resumo_assinaturas,
    top_merchants,
)
from cashlens.storage import create_db_and_tables, get_session

st.set_page_config(page_title="Cashlens", page_icon="💰", layout="wide")
create_db_and_tables()

st.title("💰 Cashlens")
st.caption("Controle financeiro pessoal local-first. Todos os dados ficam no seu SQLite local.")

hoje = date.today()
with st.sidebar:
    st.header("Período")
    ano = st.number_input("Ano", min_value=2000, max_value=2100, value=hoje.year, step=1)
    mes = st.selectbox(
        "Mês",
        options=list(range(1, 13)),
        index=hoje.month - 1,
        format_func=lambda m: calendar.month_name[m].capitalize(),
    )

with get_session() as session:
    relatorio = gerar_relatorio_mensal(session, int(ano), int(mes))
    serie = evolucao_mensal(session, date(int(ano), int(mes), 1), quantidade_meses=6)
    assinaturas = resumo_assinaturas(session)
    merchants = top_merchants(session, int(ano), int(mes))
    transacoes_mes = listar_transacoes_mensais(session, int(ano), int(mes))

col1, col2, col3 = st.columns(3)
col1.metric("Total gasto no mês", formatar_moeda(relatorio.total_centavos))
col2.metric("Assinaturas ativas (equivalente mensal)", formatar_moeda(assinaturas.total_mensal_centavos))
col3.metric("Transações não categorizadas", relatorio.nao_categorizadas_qtd)

st.divider()

col_categoria, col_evolucao = st.columns(2)

todas_categorias_do_mes = [t.categoria for t in transacoes_mes if t.categoria]
mapa_cores = cores_por_categoria(todas_categorias_do_mes)

with col_categoria:
    st.subheader("Gastos por categoria")
    if relatorio.por_categoria:
        df_categoria = pd.DataFrame(
            [{"Categoria": linha.categoria, "Total": linha.total_centavos / 100} for linha in relatorio.por_categoria]
        )
        fig_categoria = px.pie(
            df_categoria, names="Categoria", values="Total", hole=0.4, color="Categoria", color_discrete_map=mapa_cores
        )
        st.plotly_chart(fig_categoria, width="stretch")
    else:
        st.info("Sem gastos categorizados neste mês.")

with col_evolucao:
    st.subheader("Evolução mensal (últimos 6 meses)")
    df_evolucao = pd.DataFrame(
        [{"Mês": f"{ponto.mes:02d}/{ponto.ano}", "Total": ponto.total_centavos / 100} for ponto in serie]
    )
    fig_evolucao = px.bar(df_evolucao, x="Mês", y="Total")
    st.plotly_chart(fig_evolucao, width="stretch")

st.divider()

col_merchants, col_assinaturas = st.columns(2)

with col_merchants:
    st.subheader("Top merchants do mês")
    if merchants:
        df_merchants = pd.DataFrame(
            [
                {"Merchant": linha.merchant, "Total": linha.total_centavos / 100, "Compras": linha.quantidade}
                for linha in merchants
            ]
        )
        fig_merchants = px.bar(df_merchants, x="Total", y="Merchant", orientation="h", text="Compras")
        fig_merchants.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_merchants, width="stretch")
    else:
        st.info("Sem gastos neste mês.")

with col_assinaturas:
    st.subheader("Assinaturas ativas")
    if assinaturas.assinaturas:
        df_assinaturas = pd.DataFrame(
            [
                {
                    "Merchant": linha.merchant,
                    "Valor": formatar_moeda(linha.valor_centavos),
                    "Periodicidade": linha.periodicidade,
                }
                for linha in assinaturas.assinaturas
            ]
        )
        st.dataframe(df_assinaturas, width="stretch", hide_index=True)
    else:
        st.info(
            "Nenhuma assinatura ativa detectada. A detecção de recorrência exige pelo "
            "menos 2 cobranças do mesmo merchant em meses seguidos — categorizar uma "
            "transação como 'assinaturas' não é suficiente por si só. Importe mais "
            "meses de extrato pra essa detecção começar a aparecer aqui."
        )

st.divider()

st.subheader("Transações do mês")
filtro = st.text_input("Filtrar por merchant", placeholder="ex: ifood")
transacoes_filtradas = (
    [t for t in transacoes_mes if filtro.lower() in t.merchant.lower()] if filtro else transacoes_mes
)

if transacoes_filtradas:
    linhas_html = "".join(
        '<tr style="border-bottom:1px solid rgba(128,128,128,0.15);">'
        f'<td style="padding:6px 8px;">{escape(linha.data.strftime("%d/%m/%Y"))}</td>'
        f'<td style="padding:6px 8px;">{escape(linha.merchant)}</td>'
        f'<td style="padding:6px 8px;">{badge_categoria_html(linha.categoria, mapa_cores)}</td>'
        f'<td style="padding:6px 8px; text-align:right;">{escape(formatar_moeda(linha.valor_centavos))}</td>'
        "</tr>"
        for linha in transacoes_filtradas
    )
    tabela_html = (
        '<div style="max-height:480px; overflow-y:auto;">'
        '<table style="width:100%; border-collapse:collapse; font-size:0.95em;">'
        '<thead><tr style="text-align:left; border-bottom:2px solid rgba(128,128,128,0.3);">'
        '<th style="padding:6px 8px;">Data</th>'
        '<th style="padding:6px 8px;">Merchant</th>'
        '<th style="padding:6px 8px;">Categoria</th>'
        '<th style="padding:6px 8px; text-align:right;">Valor</th>'
        "</tr></thead>"
        f"<tbody>{linhas_html}</tbody>"
        "</table></div>"
    )
    st.markdown(tabela_html, unsafe_allow_html=True)
else:
    st.info("Nenhuma transação encontrada para esse filtro.")
