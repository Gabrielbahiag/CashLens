# Cashlens

Controle financeiro pessoal local-first: importa extratos bancários,
categoriza cada gasto por nicho e detecta assinaturas recorrentes
automaticamente.

Todos os dados ficam na sua máquina, em um banco SQLite local — nada é
enviado a servidores externos. Veja o plano completo em
[`PROJECT_PLAN.md`](PROJECT_PLAN.md).

## Setup

Requer [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Uso (CLI)

```bash
# Importar um extrato OFX
uv run cashlens importar caminho/para/extrato.ofx

# Importar um extrato CSV (colunas: data, descricao, valor)
uv run cashlens importar caminho/para/extrato.csv --formato csv --conta "nubank-cartao"

# Ver o relatório do mês (gastos por categoria + assinaturas ativas)
uv run cashlens relatorio 2026 6

# Ensinar uma regra pra uma transação não categorizada
uv run cashlens ensinar "padrao-do-extrato" nome-da-categoria
```

## Dashboard

```bash
uv run streamlit run src/cashlens/dashboard.py
```

Abre em `http://localhost:8501` com gráfico de gastos por categoria,
evolução mensal e a lista de assinaturas ativas — usando os mesmos dados
importados pela CLI.

## Testes

```bash
uv run pytest
```
