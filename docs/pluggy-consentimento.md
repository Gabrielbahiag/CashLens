# Open Finance via Pluggy — fluxo de consentimento

O Cashlens usa o [Pluggy](https://pluggy.ai) (produto "Meu Pluggy", gratuito
para uso pessoal) como provedor de Open Finance. Este documento explica como
uma conexão bancária é autorizada e como isso se conecta ao
`PluggyImporter` (`src/cashlens/importers/pluggy.py`).

## O que já está implementado

`PluggyImporter.sincronizar(item_id)` — dado um `item_id` (uma conexão já
consentida), autentica na API e baixa contas + transações, devolvendo o
mesmo `ExtratoImportado` que os importadores de OFX/CSV produzem. Ele **não**
implementa a interface `Importer` de arquivo, porque não faz parse de um
arquivo local — sincroniza pela rede.

**Não foi testado contra a API real do Pluggy** (exigiria uma conta e
credenciais reais, que este projeto não tem). A lógica de request/resposta,
paginação por cursor e a convenção de sinal (`DEBIT`/`CREDIT`) foi verificada
contra a documentação pública e o código-fonte do SDK oficial
(`pluggyai/pluggy-node`), e é coberta por testes com a camada HTTP mockada em
`tests/test_pluggy_importer.py`.

## O que fica pendente: capturar o `item_id`

Obter o `item_id` exige que o usuário final autorize o acesso à própria conta
bancária através do widget **Pluggy Connect**, que roda no navegador. Isso é
um fluxo web (HTML/JS), enquanto o Cashlens hoje é uma CLI local — então essa
etapa ainda não está automatizada. O passo a passo abaixo é manual, usando o
Dashboard do Pluggy, e serve tanto pra testar quanto pra uso pessoal real:

1. **Criar conta e credenciais.** Crie uma conta em pluggy.ai, crie uma
   Application no Dashboard e copie o `CLIENT_ID` e `CLIENT_SECRET`. Nunca
   commitar esses valores — vão em `.env` (veja `.env.example`).
2. **Autenticar no backend.** `POST /auth` com `{clientId, clientSecret,
   nonExpiring: false}` devolve um `apiKey` válido por 2 horas
   (`PluggyImporter._autenticar` já faz isso).
3. **Gerar um Connect Token.** `POST /connect_token` (autenticado com o
   `apiKey`) devolve um `accessToken` de curta duração (30 min), seguro pra
   expor no navegador do usuário — é o único segredo que chega ao
   client-side.
4. **Consentimento via widget.** O Connect Token é passado pro widget Pluggy
   Connect (embutido numa página web ou usando o "Preview in Demo" do
   Dashboard do Pluggy pra testar sem escrever a página). O usuário escolhe o
   banco e faz login **diretamente com o widget** — as credenciais bancárias
   nunca passam pelo backend do Cashlens.
5. **Callback com o `item_id`.** Ao concluir, o widget retorna o `item_id`
   dessa conexão. Esse é o valor que alimenta `PluggyImporter.sincronizar`.
6. **Status da conexão.** Um item pode estar `UPDATED` (sincronizado),
   `UPDATING`, `WAITING_USER_INPUT` (ex.: precisa de MFA) ou `LOGIN_ERROR`.
   `sincronizar()` assume que o item já está `UPDATED`; tratar os outros
   estados fica para quando o fluxo de consentimento for automatizado.

Pra testar sem depender do banco de verdade, o Pluggy oferece um ambiente
sandbox com instituição fictícia e credenciais `user-ok` / `password-ok`.

## Revogação de consentimento (LGPD)

O usuário pode revogar o acesso a qualquer momento deletando o item
(`DELETE /items/{id}`). Isso é responsabilidade de quem opera a integração —
o Cashlens, sendo local-first, não guarda o `apiKey` nem o `item_id` em
lugar nenhum além da chamada explícita do usuário; não há sincronização
automática em background.

## Próximo passo natural

Automatizar o passo 1–5: um comando que sobe um servidor HTTP local
temporário, abre o navegador numa página com o widget embutido, e recebe o
`item_id` de volta via callback — hoje isso é feito manualmente pelo
Dashboard do Pluggy.
