# Cashlens — Plano de Ação

> Spec mestre do projeto, feito para servir de contexto ao
> Claude Code na IDE. Leia este arquivo antes de gerar código.
>
> **O que é:** um app de controle financeiro pessoal que importa transações,
> categoriza cada gasto em um nicho (assinaturas, alimentação, serviços…),
> detecta assinaturas recorrentes automaticamente e entrega um relatório
> mensal por categoria.
>
> **Ambição:** começar como ferramenta pessoal e ser arquitetado para poder
> virar produto no futuro. Por isso: código em camadas, testável, e
> **local-first / privacy-first** desde o primeiro commit.

---

## 1. Princípios do projeto (não negociáveis)

1. **Privacy-first.** É dado financeiro. Nada de extrato real versionado no
   git. Os dados do usuário ficam na máquina dele (SQLite local). Fixtures de
   teste são sempre anonimizadas/sintéticas.
2. **Local-first.** O MVP roda 100% na máquina do usuário, sem servidor. A
   evolução para produto (nuvem, multiusuário) vem depois, sem reescrever o
   núcleo.
3. **Ingestão plugável.** Cada fonte de dados (OFX, CSV, Open Finance) é um
   adaptador que implementa a mesma interface. Adicionar fonte = novo arquivo,
   sem tocar no núcleo. (Mesmo padrão de design do RoleRush.)
4. **Núcleo independente de UI.** A lógica (importar → categorizar → relatar)
   não sabe se está sendo chamada por uma CLI, um dashboard ou uma API. Isso é
   o que permite trocar a interface quando virar produto.
5. **Determinístico e testável.** Categorização e detecção de recorrência
   precisam de testes com casos de borda. É o coração do projeto.

---

## 2. Fonte de dados — a decisão que define tudo

> Contexto importante: **não é possível capturar transações direto do Apple
> Pay** — a Apple não expõe esse histórico para apps de terceiros. O caminho
> viável no Brasil é importar extrato ou usar Open Finance.

Três formas de trazer transações, em ordem de esforço:

| Fonte | Como | Quando |
|---|---|---|
| **OFX / CSV** | Usuário exporta o extrato/fatura do banco e importa o arquivo | **MVP.** Zero burocracia, começa hoje |
| **Open Finance (Pluggy)** | Sincroniza transações via API, com consentimento | Camada "automática", diferencial de portfólio |
| Notificações/e-mail | Parsear e-mails de transação | Evolução opcional, frágil — deixar por último |

**Decisão:** MVP pela importação **OFX** (formato bancário padrão, a maioria
dos bancos BR exporta). O adaptador de Open Finance vem numa fase later,
usando o **Meu Pluggy** (gratuito para uso pessoal, com SDK oficial em
Python). Como as duas fontes passam pela mesma interface de adaptador, o
núcleo não muda quando a segunda entra.

---

## 3. Arquitetura em camadas

```
┌─────────────────────────────────────────────┐
│  Interface (CLI  →  Dashboard Streamlit)     │  troca sem mexer no núcleo
├─────────────────────────────────────────────┤
│  Núcleo (independente de UI e de fonte)      │
│   • Importação (adaptadores plugáveis)       │
│   • Normalização (limpar merchant, dedup)    │
│   • Categorização (regras → recorrência)     │
│   • Detecção de assinaturas                  │
│   • Relatórios (mensal por categoria)        │
├─────────────────────────────────────────────┤
│  Armazenamento (SQLite local)                │
└─────────────────────────────────────────────┘
        ▲                    ▲
   OFX / CSV           Open Finance (Pluggy)
   (adaptador)            (adaptador)
```

---

## 4. Estrutura de pastas sugerida

```
cashlens/
├── README.md
├── PROJECT_PLAN.md              # este arquivo
├── pyproject.toml
├── .env.example                # nomes de variáveis (sem segredos)
├── .gitignore                  # ignora *.ofx, *.csv, *.db, .env
├── config/
│   └── regras.yaml             # regras de categorização (merchant → nicho)
├── data/
│   ├── .gitkeep
│   └── (extratos e cashlens.db ficam aqui — NUNCA versionados)
├── src/
│   └── cashlens/
│       ├── __init__.py
│       ├── models.py           # Transacao, Categoria, Regra, Assinatura, Conta
│       ├── config.py           # carrega regras.yaml e settings
│       ├── storage.py          # camada SQLite (SQLModel/SQLAlchemy)
│       ├── importers/
│       │   ├── base.py         # interface Importer (abstract)
│       │   ├── ofx.py
│       │   ├── csv.py
│       │   └── pluggy.py       # fase later (Open Finance)
│       ├── normalize.py        # limpeza de nome de merchant + dedup
│       ├── categorize.py       # motor de regras
│       ├── recurrence.py       # detecção de assinaturas/recorrência
│       ├── reports.py          # agregações e relatório mensal
│       ├── cli.py              # entrypoint de linha de comando
│       └── dashboard.py        # app Streamlit (fase later)
└── tests/
    ├── fixtures/               # extratos SINTÉTICOS, nunca reais
    │   ├── exemplo.ofx
    │   └── exemplo.csv
    ├── test_importers.py
    ├── test_normalize.py
    ├── test_categorize.py
    ├── test_recurrence.py
    └── test_reports.py
```

---

## 5. Modelo de dados

**Transacao** (unidade central):
- `id` — id estável para dedup (hash de data+valor+descrição+conta, ou id da fonte)
- `data`
- `valor` (negativo = saída, positivo = entrada)
- `descricao_original` — texto cru do extrato
- `merchant` — nome limpo/normalizado (ex: "IFD*IFOOD" → "iFood")
- `categoria` — preenchido pela categorização
- `conta` — de qual conta/cartão veio
- `fonte` — ofx, csv, pluggy
- `assinatura_id` — vínculo opcional se for parte de uma recorrência

**Categoria**: nome do nicho (assinaturas, alimentação, transporte, serviços, mercado, saúde, lazer, contas…). Lista configurável.

**Regra**: padrão → categoria. Ex: contém "spotify" → assinaturas; "ifood"/"rappi" → alimentação.

**Assinatura**: merchant + valor recorrente + periodicidade + status (ativa/cancelada), inferida pelo motor de recorrência.

**Conta**: identificação da conta/cartão de origem.

---

## 6. Motor de categorização (o coração)

Evolução em três níveis — implementar nesta ordem:

1. **Regras declarativas** (`config/regras.yaml`). Casamento por substring/regex
   no `merchant`/`descricao`. Simples, transparente, fácil de o usuário editar.
   ```yaml
   categorias:
     assinaturas:
       - spotify
       - netflix
       - "google.*one"
     alimentacao:
       - ifood
       - rappi
       - "rest(aurante)?"
     transporte:
       - uber
       - "99.*app"
   ```
2. **Fallback "não categorizado"** + comando pra o usuário revisar e ensinar
   novas regras (o app sugere, o usuário confirma, a regra é salva).
3. **(Evolução) ML** para classificar merchants desconhecidos, treinado nas
   categorizações já confirmadas pelo usuário. Deixar como fase avançada — as
   regras já contam a história no portfólio.

---

## 7. Detecção de assinaturas (a feature que brilha)

Resolve diretamente o "meus gastos com assinatura no fim do mês". É um
algoritmo de verdade, ótimo pra entrevista.

Lógica: agrupar transações por `merchant`; dentro do grupo, procurar cobranças
com **valor semelhante** (tolerância pequena) em **intervalos regulares**
(mensal/anual). Sinalizar como assinatura provável quando houver 2+
ocorrências no padrão. Detectar também **aumento de preço** (mesma assinatura,
valor subiu) e **assinatura fantasma** (recorrência ativa que o usuário talvez
esqueceu). Tudo isso vira insight no relatório.

---

## 8. Relatórios

- Total gasto no mês, quebrado por categoria (com % do total).
- Evolução mês a mês por categoria.
- Bloco "Assinaturas" com total mensal recorrente e lista de cobranças ativas.
- Top merchants do mês.
- Um "resumo do mês" textual (ex: "Você gastou R$ X em alimentação, Y% a mais
  que no mês passado").

MVP entrega isso na CLI (tabela no terminal). A fase de dashboard leva pro
Streamlit com gráficos.

---

## 9. Stack

`python` · `pydantic` (modelos) · `SQLModel` ou `SQLAlchemy` + `sqlite3` ·
`pandas` (agregações) · `ofxparse`/`ofxtools` (leitura OFX) · `PyYAML`
(regras) · `typer` ou `click` (CLI) · `streamlit` + `plotly` (dashboard,
fase later) · `pluggy-sdk` (Open Finance, fase later) · `pytest`.

---

## 10. Privacidade e segurança (levar a sério)

- `.gitignore` bloqueia `*.ofx`, `*.csv`, `*.db`, `.env` desde o primeiro commit.
- Segredos (credenciais do Pluggy) só em variável de ambiente / `.env` local.
- Testes usam **fixtures sintéticas** — nunca extratos reais.
- Dados do usuário nunca saem da máquina no MVP.
- Se virar produto: consentimento explícito, criptografia em repouso,
  conformidade com a LGPD. Documentar isso já mostra maturidade.

---

## 11. Roadmap em fases (checklist)

### Fase 0 — Fundação
- [x] Repo, `pyproject.toml`, venv, deps, `.gitignore` com regras de dado sensível
- [x] `models.py` (Transacao, Categoria, Regra, Conta)
- [x] `storage.py` com SQLite + esquema inicial
- [x] pytest rodando

### Fase 1 — Importação OFX end-to-end
- [x] `importers/base.py` (interface `Importer`)
- [x] `importers/ofx.py` lendo e mapeando para `Transacao`
- [x] Dedup na importação (não duplicar transação já vista)
- [x] Fixture OFX sintética + testes

### Fase 2 — Normalização + categorização
- [x] `normalize.py` (limpeza de merchant)
- [x] `config/regras.yaml` + `categorize.py` (motor de regras)
- [x] Fluxo "não categorizado → usuário ensina regra"
- [x] Testes de categorização com casos de borda

### Fase 3 — Relatório mensal (CLI)
- [x] `reports.py` (agregação por categoria/mês)
- [x] `cli.py`: importar arquivo e ver o relatório no terminal

### Fase 4 — Detecção de assinaturas
- [ ] `recurrence.py` (agrupamento + regularidade + tolerância de valor)
- [ ] Bloco de assinaturas no relatório
- [ ] Testes com séries recorrentes sintéticas

### Fase 5 — Importador CSV
- [ ] `importers/csv.py` (bancos que exportam CSV em vez de OFX)

### Fase 6 — Dashboard (Streamlit)
- [ ] `dashboard.py`: gráficos por categoria, evolução mensal, assinaturas
- [ ] README com print/GIF do dashboard

### Fase 7 — Open Finance (Pluggy) — o diferencial "produto"
- [ ] `importers/pluggy.py` via Meu Pluggy (sync automático)
- [ ] Fluxo de consentimento documentado

### Evoluções de produto (roadmap pra contar na entrevista)
- [ ] Orçamentos por categoria + alertas de estouro
- [ ] Categorização por ML nos merchants desconhecidos
- [ ] Multiusuário / versão web (FastAPI + front)

---

## 12. Gotchas

- **Formato OFX é chato:** encoding, datas e sinais variam por banco.
  Normalizar tudo ao mapear para `Transacao`.
- **Dedup:** reimportar o mesmo extrato não pode duplicar transações. Chave
  estável resolve; testar.
- **Categorização é iterativa:** vai errar no começo. O fluxo de "usuário
  confirma e vira regra" é o que faz melhorar — priorizar isso, não perseguir
  100% de acerto automático.
- **Recorrência tem falso positivo:** compra parcelada parece assinatura.
  Distinguir (parcelas têm fim e costumam vir marcadas) faz parte do desafio.
- **Nunca commitar dado real.** Conferir o `.gitignore` antes do primeiro push.

---

## 13. Definição de "MVP pronto"

Consigo **importar um extrato OFX**, ver minhas transações **categorizadas por
nicho**, receber um **relatório mensal por categoria** e uma **lista de
assinaturas detectadas** — tudo pela CLI, com dados ficando só na minha
máquina, e com testes cobrindo importação, categorização e recorrência.
