import calendar
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from cashlens.formatting import formatar_moeda
from cashlens.reports import evolucao_mensal, gerar_relatorio_mensal, resumo_assinaturas
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

col1, col2, col3 = st.columns(3)
col1.metric("Total gasto no mês", formatar_moeda(relatorio.total_centavos))
col2.metric("Assinaturas ativas (equivalente mensal)", formatar_moeda(assinaturas.total_mensal_centavos))
col3.metric("Transações não categorizadas", relatorio.nao_categorizadas_qtd)

st.divider()

col_categoria, col_evolucao = st.columns(2)

with col_categoria:
    st.subheader("Gastos por categoria")
    if relatorio.por_categoria:
        df_categoria = pd.DataFrame(
            [{"Categoria": linha.categoria, "Total": linha.total_centavos / 100} for linha in relatorio.por_categoria]
        )
        fig_categoria = px.pie(df_categoria, names="Categoria", values="Total", hole=0.4)
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
    st.info("Nenhuma assinatura ativa detectada.")
