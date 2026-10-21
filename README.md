# MilioAI — atendimento guiado

React + FastAPI + LangGraph + PostgreSQL/pgvector + Ollama local. A interface Demà foi preservada. A entrega atual oferece oito assuntos, perguntas guiadas e perguntas livres, com respostas fundamentadas e fontes na própria mensagem.

## Demonstração offline (sem backend)

Neste computador, o `package.json` está em `C:\Users\dougl\Downloads\MilioAI\MilioAI` (há duas pastas com o mesmo nome). Execute:

```powershell
cd C:\Users\dougl\Downloads\MilioAI\MilioAI
npm run dev:offline
```

Abra [http://127.0.0.1:5173](http://127.0.0.1:5173). Encerre outro Vite que esteja usando essa porta antes de iniciar. As dependências já estão instaladas; somente em uma instalação nova, execute `npm ci` com acesso à internet primeiro. Não precisa de `.env`, login, credenciais, FastAPI, Docker, PostgreSQL, Supabase ou Ollama.

O mesmo frontend utiliza um adaptador local com oito assuntos, perguntas guiadas, conversas (criar, selecionar, renomear, excluir e continuar), instrutores fictícios com e sem contato, e cartões fictícios pesquisáveis. No controle **Demonstração local**, escolha resposta curta, com fontes, longa, sem informações, falha controlada ou processamento lento; envie qualquer mensagem para executar o cenário. O fluxo guiado de **Falta no Curso** apresenta instrutores; **Benefício Vale-Transporte** apresenta cartões. Os fluxos guiados mantêm textos próprios, e o cenário de falha pode interrompê-los. Use processamento lento e **Cancelar processamento** para testar interrupções.

São fixtures determinísticas, sem IA, RAG ou solicitações reais. O botão `+` permanece visível, desabilitado com indicação acessível; arquivos não são enviados nem armazenados. Mensagens e conversas ficam apenas no namespace `milioai.demo.offline.v1` do localStorage. **Limpar demonstração** remove somente esse namespace. Esse armazenamento não é seguro nem corporativo: use somente conteúdo fictício. A sessão corporativa e as chaves de armazenamento normais não são lidas ou modificadas pelo adaptador offline.

`src/api/client.ts` seleciona centralmente o adaptador; `src/api/remote.ts` preserva o cliente real; `src/offline/` contém fixtures, persistência e controles. O Vite ativa a demonstração exclusivamente com `serve --mode offline`, remove o proxy nesse modo e escuta somente em loopback. `npm run dev` mantém a API/autenticação existentes. `npm run build` elimina o adaptador e os controles offline; `vite build --mode offline` é recusado. Nenhuma autenticação do backend foi alterada.

Verificações do frontend: `npm run typecheck`, `npm run lint`, `npm test` e `npm run build`. O teste `npm run test:offline:browser` inicia e encerra seu próprio Vite e usa Edge headless (ou `PLAYWRIGHT_CHANNEL`) para exercitar os fluxos, bloquear e registrar qualquer chamada externa ou `/api`, conferir recarga e isolamento das sessões. Não deixe outro servidor na porta 5173 ao executá-lo. Os testes de navegador normais abaixo continuam dependendo do backend real.

## Executar a configuração local já preparada

```powershell
# Na pasta que contém package.json e docker-compose.yml:
docker compose up -d db api
npm run dev
```

Abra o endereço informado pelo Vite, normalmente [http://127.0.0.1:5173](http://127.0.0.1:5173). Não é necessário rodar `npm ci` a cada execução. Se precisar reinstalar dependências, encerre primeiro o Vite com Ctrl+C para liberar o esbuild no Windows. Não apague node_modules nem reinstale enquanto o servidor estiver aberto.

O `.env` local já usa o corpus do PDF fornecido, em versão e escopo de validação separados da base fictícia anterior. Nenhuma conversa antiga foi apagada ou migrada silenciosamente.

## Instalação inicial e indexação do PDF

Requer Docker Desktop, Node.js 22.13+ ou 24 LTS e Ollama. Python 3.12 é executado em container; o Python 3.15 do Windows não é necessário.

```powershell
./scripts/init-local.ps1
ollama pull qwen3:4b-instruct
ollama pull nomic-embed-text-v2-moe
npm ci
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
```

Antes da ingestão local, ajuste estas entradas em `.env`, preservando os segredos aleatórios gerados:

```dotenv
ACTIVE_KB_VERSION=folha-ponto-local-v1
RAG_PROFILE=sections-v3-contextual
RAG_TOP_K=3
RAG_MAX_DISTANCE=0.55
DEV_DOCUMENT_SCOPES=["local_review"]
EMBEDDING_QUERY_PREFIX="search_query: "
EMBEDDING_DOCUMENT_PREFIX="search_document: "
```

Mantenha `APP_ENV=development` e `AUTH_MODE=development` somente no ambiente local. Indexe o arquivo autorizado com montagem somente para leitura:

```powershell
$pdfPath = 'C:/Users/douglas.amaral/Downloads/ORIENTAÇÕES PARA PREENCHIMENTO DA FOLHA PONTO.pdf'
docker compose run --rm -v "${pdfPath}:/input/folha-ponto.pdf:ro" api python -m app.rag.ingest /input/folha-ponto.pdf --approve --local-review --scope local_review --display-name 'ORIENTAÇÕES PARA PREENCHIMENTO DA FOLHA PONTO.pdf'
docker compose up -d api
npm run dev
```

O PDF não é incorporado à imagem Docker, ao frontend ou ao repositório. O original e o texto indexado ficam em armazenamento privado e PostgreSQL. A reingestão inalterada reconhece o registro existente. O escopo `local_review` e `validation_only` restringem este documento ao desenvolvimento até confirmação administrativa de vigência e autorização institucional.

## Primeiro uso

Crie uma conversa, selecione **Folha Ponto** e **Qual é o prazo de entrega da folha ponto?**. A pergunta é resolvida no backend pelo identificador, passa pelo LangGraph, recupera o documento e gera resposta real com seção e página. Depois digite **“E se eu atrasar?”**, escolha outra pergunta ou use **Voltar aos assuntos**.

**Outros** permite escrever livremente e oferece atalhos para calendário, férias e documentos escolares. Consultas operacionais ao Conecta Jovem seguem o catálogo estruturado; regras, prazos e políticas continuam no RAG ou no fallback existente. Atestados usam somente o que estiver documentado; o PDF não é uma política completa de entrega de atestados.

O botão `+` mantém upload privado de PDF/TXT/Markdown. Anexos não são interpretados pela IA nem entram automaticamente no corpus institucional.

## Verificações

```powershell
npm run typecheck
npm run lint
npm test
npm run build
docker compose exec api ruff check app tests migrations
docker compose exec api mypy app
docker compose exec api alembic check
# Testes isolados + PostgreSQL + o PDF real já indexado:
docker compose exec -e RUN_DB_TESTS=1 -e RUN_RAG02_LIVE=1 api pytest -q
# Avaliação real de recuperação, sem guardar consultas de usuários:
docker compose exec api python -m app.rag.evaluate
# API e Vite ativos, Edge instalado:
$env:PLAYWRIGHT_CHANNEL='msedge'
npm run test:browser
```

`RUN_LIVE_TESTS=1` também habilita os dois testes da entrega anterior, que usam a base fictícia legada separada (`test-v1`, perfil `legacy`). Essa base não é usada pelo atendimento atual. Os testes de RAG 02 utilizam o PDF fornecido; testes isolados podem usar mocks, a aplicação não.

## Documentação

- [RAG 02: arquitetura, avaliação, arquivos e limitações](docs/RAG02.md).
- [Configuração detalhada do backend e Supabase](docs/BACKEND-SETUP.md), incluindo JWT/JWKS, OTP e concessão administrativa de escopos. Os exemplos de conversa fictícia nesse documento são históricos.
- [.env.example](.env.example), sem segredos reais.

Supabase real não foi provisionado. O modo local usa uma identidade de desenvolvimento explicitamente habilitada; a autorização documental continua no backend. Em produção, configure JWT assinado, banco privado, escopos administrativos e HTTPS. Documentos `validation_only` são excluídos da recuperação fora do desenvolvimento, independentemente do tópico escolhido.

- [Orientações operacionais e fluxo de instrutores](docs/OPERATIONAL-SUPPORT.md).

- [RAG de segunda via do vale-transporte](docs/VT-SEGUNDA-VIA.md).

- [Sprint de UX conversacional: cópia, rolagem e feedback](docs/UX-SPRINT.md). Execute `npm run test:ux:browser` para validar as interações no Edge, sem backend; mantenha as portas 5173 e 5174 livres.
