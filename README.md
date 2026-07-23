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

## Testes

```bash
uv run pytest
```
