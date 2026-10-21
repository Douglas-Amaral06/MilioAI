# Conecta Jovem e atendimento educacional

## Implementação

A evolução usa a API, o catálogo, o LangGraph, o PostgreSQL e o frontend existentes. Não adiciona dependências ou serviços. Migração aditiva `0003` acrescenta `conversations.support_state`; não modifica documentos, embeddings nem mensagens históricas.

`backend/app/support/operational_guidance.json` centraliza URL e label do Conecta Jovem, oito serviços, diretório de 16 instrutores, contatos do Educacional, habilitação, origem, data e status de validação. Os metadados comuns se aplicam a todos os registros. Serviços: gerar folha, calendário, férias no calendário, enviar folha assinada, documentos escolares, atestado do trabalho, atestado do curso e holerite. As mensagens são montadas pelo servidor com a URL única configurada; o modelo não gera links ou contatos.

## Roteamento e estado

O nó `operational_router` antecede a classificação documental existente. Perguntas guiadas usam IDs canônicos validados no servidor e dispensam LLM. Respostas explícitas à confirmação também dispensam LLM. Perguntas livres usam classificação semântica no Ollama com saída JSON restrita a intenções cadastradas e exemplos de calibração. Salvaguardas conservadoras separam políticas de consultas operacionais e impedem que um pedido genérico de documento herde automaticamente um serviço anterior. Não há identificação exclusivamente por frases exatas.

Orientações cadastradas seguem para `operational`, sem busca vetorial. Regras, prazos, assinaturas e perguntas sem intenção operacional seguem pelo fluxo existente de classificação, recuperação, avaliação de suficiência, geração e validação de fontes. Falha de classificação retorna ao fluxo documental. Perguntas documentais sobre falta no curso são respondidas e têm fontes validadas antes da confirmação do instrutor.

O estado persistido contém `asked`, `stage` (idle, confirmation, selection, contact), `selected_instructor_id` e metadados operacionais quando aplicáveis. A confirmação ocorre uma vez por conversa; outro assunto suspende a seleção e preserva a possibilidade de retomada. Ações estruturadas preservam o assunto selecionado. A escolha anterior é reutilizada em novas orientações pertinentes, sem exigir nova seleção. Cancelamento não encerra a conversa. Histórico e estado permanecem associados ao proprietário autenticado.

Ações são enviadas pelo endpoint de mensagens/stream existente: `instructor_known`, `instructor_unknown`, `instructor_select`, `instructor_cancel`, `instructor_resume`. Somente a seleção aceita `instructor_id`. O servidor valida escopo, etapa e ID; não aceita nome, e-mail, texto ou anexos junto à ação. O estado só é alterado após resposta concluída. O bloqueio de conversa e a proteção contra requisições duplicadas continuam ativos.

## Diretório, autorização e atualização

`GET /api/v1/support/instructors` exige autenticação e escopo administrativo `education:contacts`; retorna apenas IDs e nomes habilitados. Contatos são resolvidos somente no backend após seleção. Nenhum cabeçalho ou campo do frontend concede autorização. O modo local continua exigindo o token de desenvolvimento e respeita também os escopos cadastrados no usuário pelo administrador.

A identidade local foi autorizada para validar esta entrega. Para outras identidades, após autenticação, use o comando administrativo existente, preservando os demais escopos necessários (o comando substitui a lista):

```powershell
docker compose exec api python -m app.auth.grant --identity IDENTIDADE --scope education:contacts --scope ESCOPO_DOCUMENTAL_EXISTENTE
```

Para atualizar contatos, edite os registros em `operational_guidance.json`, preserve IDs estáveis, mantenha `email: null` enquanto não confirmado e atualize data/origem/status. `enabled: false` remove um instrutor das opções e impede nova resolução desse registro. Letícia da Silva Lima permanece sem e-mail; a resposta encaminha ao Educacional. Não se inferem contatos pelo nome. O telefone é link de chamada, sem alegação de WhatsApp.

Para atualizar o portal, altere `portal_url` uma única vez; a validação exige HTTPS e o host institucional permitido. Novo host exige revisão da lista permitida em `operational.py`. Novos serviços também exigem ampliar intenções, classificação e testes; a atualização de nomes e e-mails não exige mudanças no LangGraph. Após alterações de configuração, reconstrua/reinicie a API local.

## Frontend

`InstructorFlow` mostra confirmação, busca de nomes sem distinção de acentos, lista compacta com botões acessíveis por teclado, contato ausente, cancelamento, repetição de carregamento em caso de erro e retomada. A busca é local sobre os nomes autorizados recebidos do servidor, não sobre e-mails. O componente é ligado ao estado persistido da conversa pelo hook existente.

O renderizador Markdown seguro existente mostra o Conecta Jovem em `#402FDD`, além de `mailto:` e `tel:`. Links externos usam `noopener noreferrer`; HTML não é interpretado. Fontes documentais permanecem junto à resposta RAG. Sidebar, Space Grotesk, composer fixo, anexos e alinhamento das mensagens foram preservados.

## Validação institucional e conflito documental

A configuração está marcada `validation_status: pending`. Ela funciona no ambiente de desenvolvimento; fora dele fica desabilitada até validação institucional explícita registrada como `validated`. Não houve deploy em produção.

O PDF anterior de Folha Ponto pode indicar canais de entrega diferentes da orientação operacional fornecida agora para Conecta Jovem. Os dados históricos continuam íntegros no RAG. A orientação de envio de folha e atestado do curso inclui confirmação do procedimento vigente com a área responsável; não afirma desativação ou substituição dos canais anteriores. O portal e o envio ao instrutor não são apresentados como substitutos entre si.

Antes do uso corporativo, confirmar com as áreas responsáveis: disponibilidade de cada um dos oito serviços no portal, compatibilidade dos canais de envio, atualidade dos 15 e-mails fornecidos, contato ausente de Letícia, telefone/e-mail do Educacional e quais perfis receberão o escopo. Nenhum menu interno ou procedimento adicional foi inventado.

## Testes e evidências

- Frontend: 16 testes Vitest; build TypeScript/Vite e ESLint.
- Backend: suíte com testes isolados, PostgreSQL, classificação real Ollama e RAG real do PDF. Resultado final: **77 aprovados, 2 ignorados** (testes legados optativos da base fictícia, habilitados separadamente por `RUN_LIVE_TESTS`). Inclui os oito cenários reais de RAG 02 e os 16 testes reais de orientações operacionais.
- Segurança: acesso anônimo (401), usuário sem escopo (403), conversa de outro usuário (404), ID inexistente (422), etapa inválida (409), contatos sem vazamento na lista e HTML/links seguros.
- Regressão de navegador anterior: **PASS**, incluindo clique triplo com envio único, SSE, fontes, persistência, troca de assunto, upload/remoção de anexo e viewports compactos. O teste foi ajustado para nove perguntas de Folha Ponto e espera explícita do fim do carregamento.
- Edge real: link exato e cor institucional, 16 nomes, busca e teclado, persistência ao recarregar, contato de Marcio, Letícia sem contato, instrutor desconhecido, mudança para holerite, não repetição, cancelamento/retomada, esclarecimento de documento ambíguo e fontes do PDF.
- Layout: 1440×900, 1366×768, 390×844 e altura reduzida 390×400, sem rolagem global, com compositor visível. Capturas locais em `tmp/operational-qa/`; não representam validação de teclado físico de celular.

```powershell
npm test
npm run build
npm run lint
npm run test:operational:browser
# API/Vite ativos para testes do navegador.
docker compose exec -e RUN_DB_TESTS=1 -e RUN_OPERATIONAL_LIVE=1 -e RUN_RAG02_LIVE=1 api pytest -q
docker compose exec api ruff check app tests migrations
docker compose exec api mypy app
docker compose exec api alembic check
```

Limitações: a classificação semântica do modelo local pode errar formulações não avaliadas; os testes cobrem os exemplos obrigatórios e variações, mas não garantem todas as formas de linguagem. Classificação indisponível segue o fluxo documental. Não foram validados login real no Conecta Jovem, disponibilidade interna dos serviços, envio de e-mails ou chamadas telefônicas. A migração foi aplicada apenas no PostgreSQL local.

## Arquivos

Criados: `backend/app/support/operational.py`, `operational_guidance.json`, `backend/migrations/versions/0003_operational_support.py`, `backend/tests/test_operational.py`, `test_operational_integration.py`, `test_operational_live.py`, `src/components/InstructorFlow.tsx`, `InstructorFlow.test.tsx`, `scripts/operational-browser-check.cjs` e este relatório.

Modificados: catálogo e grafo; schemas, modelos e serviço de mensagens; rotas e autorização; empacotamento Python para incluir JSON; fixtures/testes anteriores para a nova interface de classificação e catálogo; tipos, cliente API, hook, ações de workspace, App, Chat, CSS, menu de assuntos e validação de links; scripts npm e README. Os documentos BACKEND-SETUP, BACKEND-VALIDATION e RAG02 receberam somente normalização de formatação Prettier.

Evidência visual local: [busca de instrutores no mobile](../tmp/operational-qa/instructors-mobile.png). Os contatos não foram incorporados ao bundle do frontend.
