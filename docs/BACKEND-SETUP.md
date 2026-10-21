# MilioAI

Assistente corporativo com React/TypeScript e identidade Demà. Implementação local: **React → FastAPI → LangGraph → RH Frequência → RAG/pgvector → Ollama → fontes → PostgreSQL**. Apenas o agente `rh_frequency` está ativo. Nenhuma API paga, política real inventada ou publicação externa.

## Executar localmente (PowerShell)

Requisitos: Docker Desktop ativo, Node.js 22.13+ ou 24 LTS, Ollama instalado. O backend usa Python **3.12 no container**; não depende do Python 3.15 do Windows.

```powershell
# Na pasta que contém package.json e docker-compose.yml:
./scripts/init-local.ps1
ollama pull nomic-embed-text-v2-moe
ollama pull qwen3:4b-instruct
docker compose build api
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.rag.ingest fixtures/frequency-test.md --approve --scope test --test
docker compose up -d api
npm ci
npm run dev
```

Abra [MilioAI](http://127.0.0.1:5173) e [OpenAPI local](http://127.0.0.1:8000/docs). Portas: Vite 5173, API 8000, PostgreSQL local 5433. Se um Vite antigo estiver ativo, encerre-o antes de iniciar esta versão. Não mantenha duas instâncias na mesma porta.

O script cria `.env` somente se ele não existir, com segredos aleatórios e `APP_ENV=development`, `AUTH_MODE=development`. Credenciais nunca são impressas nem incluídas no build. O proxy Vite local injeta o token no servidor apenas com esse modo explicitamente habilitado, verifica a origem do navegador e não faz isso em build/produção. Todos os usuários desse modo local compartilham uma identidade de desenvolvimento com escopo **test**. Não exponha esse ambiente na rede. A API recusa o modo de desenvolvimento se `APP_ENV` não for `development` ou se faltar token de pelo menos 32 caracteres.

O `.env` local já preparado nesta entrega usa esse modo. `.env.example` começa em `AUTH_MODE=jwt`, sem segredos. PostgreSQL e arquivos ficam em volumes Docker persistentes; `docker compose down` mantém os dados. Não use `down -v` se precisar preservá-los.

## Primeira conversa real

Pergunte: **“No documento fictício de teste, qual o prazo para enviar um atestado após o retorno?”** A resposta deve citar o prazo de 3 dias úteis, identificar o material como fictício e mostrar fontes expansíveis na própria mensagem. Recarregue a página: conversa, resposta e fontes devem permanecer.

O documento `backend/fixtures/frequency-test.md` é fictício e não tem validade institucional. O botão `+` aceita PDF com texto, TXT e Markdown, até 5 MB por arquivo e cinco anexos por mensagem. É possível remover antes de enviar. Arquivos enviados ficam privados, vinculados ao usuário/conversa e **não são interpretados pela IA nem indexados no conhecimento institucional**.

O `qwen3:4b` instalado inicialmente produziu análise em vez da resposta final no teste local, mesmo com `think:false` e `/no_think`. Por isso o padrão validável foi alterado para `qwen3:4b-instruct`, preservando o modelo anterior. Geração: contexto 4096, limite 600 tokens, temperatura zero; parâmetros configuráveis. Embeddings: `nomic-embed-text-v2-moe:latest`, **768 dimensões verificadas por resposta real**; prefixos `search_query:` e `search_document:`. O modelo de embeddings é descarregado após o uso para liberar VRAM.

## Configuração e instalação alternativa

As configurações estão em [.env.example](../.env.example). Dependências Python diretas em `backend/pyproject.toml`; versões exatas, inclusive transitivas, em `backend/requirements.lock`. O Docker instala o lock e a aplicação sem resolver versões novamente. Para rodar fora do container, use Python 3.12–3.14, venv, `pip install -r requirements.lock`, `pip install --no-deps -e .`, e configure o ambiente. No host, use `OLLAMA_URL=http://127.0.0.1:11434`, `STORAGE_PATH` privado local e `DATABASE_URL` apontando para `127.0.0.1:5433`. Execute `alembic upgrade head` e `uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` dentro de `backend/`.

## Supabase e autenticação corporativa

Nenhum recurso remoto foi criado. Para usar um projeto existente:

1. Em `.env`, configure `AUTH_MODE=jwt`, `JWT_ISSUER` como a URL do projeto seguida de `/auth/v1`, `JWT_JWKS_URL` com `/auth/v1/.well-known/jwks.json` e `JWT_AUDIENCE=authenticated`. Utilize chaves assimétricas RS256/ES256. Projetos que ainda usam apenas HS256 precisam migrar as chaves; não aceitamos tokens apenas decodificados ou segredos compartilhados no frontend.
2. Configure `VITE_SUPABASE_URL` e `VITE_SUPABASE_PUBLISHABLE_KEY` com os valores públicos do projeto. Nunca use service-role/secret key no navegador. Habilite Email OTP no Supabase e inclua o código `{{ .Token }}` no template de e-mail. Usuários devem existir previamente; a aplicação usa `create_user:false`. O formulário solicita e valida o código usando Supabase Auth real.
3. Use `APP_ENV=production` no ambiente publicado, uma origem HTTPS explícita em `CORS_ORIGINS` e um proxy HTTPS de mesma origem encaminhando `/api` à API. O proxy Vite de desenvolvimento não integra o artefato estático de produção. A sessão Supabase usa `sessionStorage`, com renovação de token; configure CSP e proteção contra XSS no host publicado. Sair remove a sessão desta aba.
4. Opcionalmente, aponte `DATABASE_URL` ao PostgreSQL Supabase usando `postgresql+psycopg://` e `sslmode=require`, preferencialmente conexão direta ou pooler em modo sessão para migrations. Habilite `vector` com uma conta administrativa e execute Alembic. Não existe sincronização com o banco local. Credenciais de banco ficam somente no backend.
5. Após o primeiro login, o usuário existe em `users`, inicialmente sem escopos documentais. Conceda acesso pelo comando administrativo, nunca via metadados editáveis do usuário:

```powershell
docker compose run --rm api python -m app.auth.grant --identity "EMISSOR:UUID_DO_USUARIO" --scope rh_frequency
```

`EMISSOR` deve ser o valor exato de `JWT_ISSUER`. Para o corpus fictício, conceda `--scope test` explicitamente. Conversas são sempre filtradas pelo proprietário; acesso a um UUID de outro usuário retorna 404. Escopos são mantidos pelo backend, não recebidos do cliente. As tabelas próprias da aplicação devem permanecer inacessíveis à API pública de dados do Supabase: não conceda privilégios a `anon`/`authenticated`; mantenha a conexão do backend privada. Prepare papel SQL de execução com privilégios mínimos separado do papel administrativo de migrations antes de produção.

## Ingestão institucional

Comando administrativo, sem rota pública de aprovação:

```powershell
docker compose run --rm api python -m app.rag.ingest CAMINHO_NO_CONTAINER --approve --scope rh_frequency
```

Monte o diretório autorizado somente na execução administrativa. O CLI valida arquivo, extrai texto, divide em trechos, gera embeddings e persiste documento aprovado + vetores atomicamente. Um mesmo hash/versão/escopo/modelo não é indexado duas vezes. PDF digitalizado sem texto, protegido ou acima dos limites é rejeitado; não há OCR.

A recuperação aplica aprovação, domínio, escopo do usuário, versão ativa (`ACTIVE_KB_VERSION`), modelo e dimensão **antes** da distância cosseno. Até quatro trechos, limiar `RAG_MAX_DISTANCE=0.45`. Não há índice ANN neste corpus pequeno: a busca vetorial exata evita índices incompatíveis. Trocar modelo, dimensão ou prefixos exige uma nova versão da base e reingestão, sem misturar espaços de embeddings. Por ser um tag mutável, fixe também a revisão/digest do modelo em ambientes controlados.

## API e persistência

`/api/v1`: health, ready autenticado, me, CRUD de conversas, listagem de mensagens, envio normal ou streaming, upload/listagem/download privado/remoção de anexo pendente. OpenAPI descreve os contratos. Listagens usam `limit` (1–100) e `offset`. Conteúdo de mensagem até 4000 caracteres; títulos até 100. UUIDs de requisição evitam mensagens duplicadas: repetir retorna 409; o cliente deve recarregar o histórico antes de decidir reenviar.

`POST /conversations/{id}/messages` e `/stream` são duas representações da mesma operação. Não chame ambos para a mesma pergunta. A interface usa exclusivamente `/stream`, via `fetch` autenticado e SSE. Eventos: `start`, `delta`, `sources`, `done`, `error`. Deltas são provisórios; somente `done` confirma resposta validada e persistida. Raciocínio do provedor, prompts e detalhes internos não fazem parte do contrato.

Uma mensagem do usuário e uma resposta `processing` são gravadas antes da geração. A resposta é persistida uma vez, após validar fontes; em erro/cancelamento fica vazia com status `failed`/`cancelled`. Bloqueio por conversa e índice parcial impedem gerações concorrentes na mesma conversa. Timeout total configurável; o fluxo fecha a conexão ao Ollama em desconexões. Execuções abandonadas por morte do processo são marcadas como falha após timeout + 60 segundos ao consultar/enviar; recarregar acompanha `processing` por polling. Renomear/excluir durante geração retorna 409.

PostgreSQL é a única fonte de verdade do histórico. Não há checkpointer LangGraph duplicando mensagens. O contexto inclui no máximo 16 mensagens concluídas e 4000 caracteres; RAG é separado da memória. Rascunhos são independentes em memória por conversa nesta primeira integração. O antigo `milioai.workspace.v1` fica intacto no navegador, separado e não importado; `src/data` permanece apenas para leitura futura do legado e testes históricos.

## Testes

```powershell
npm run typecheck
npm run lint
npm test
npm run build
docker compose run --rm api ruff check app tests migrations scripts
docker compose run --rm api mypy app
docker compose run --rm -e RUN_DB_TESTS=1 api pytest -q
# Requer Ollama ativo e corpus fictício ingerido:
docker compose run --rm -e RUN_LIVE_TESTS=1 api pytest -q -m live
# API e Vite ativos, Edge instalado:
$env:PLAYWRIGHT_CHANNEL='msedge'
npm run test:browser
```

Os testes de banco criam e removem apenas seus registros de teste; não limpam tabelas inteiras. Testes isolados podem usar mocks; a aplicação executada não tem modelo ou banco falso. A suíte do navegador envia perguntas reais e cria uma conversa de validação no usuário local. Capturas em `docs/qa/`. `BASE_URL` permite outro endereço local.

Resultados e limitações efetivamente verificados estão em [docs/BACKEND-VALIDATION.md](BACKEND-VALIDATION.md).

## Arquitetura e evolução

```text
backend/
  app/
    api/             rotas versionadas e contratos Pydantic
    core/            configuração e erros controlados
    auth/            verificação JWT/JWKS e concessão administrativa de escopos
    db/              modelos SQLAlchemy e sessões
    conversations/   autorização e acesso às conversas
    messages/        transação de envio, SSE e estados de execução
    agents/          instruções e políticas RH Frequência
    orchestration/   grafo LangGraph e registro de agentes
    rag/             ingestão e recuperação autorizada
    llm/             cliente Ollama HTTP e contratos
    storage/         arquivos privados e extração PDF isolada
  migrations/        revisão inicial Alembic com pgvector
  tests/             testes isolados, PostgreSQL e integração Ollama
  fixtures/          material fictício explícito
src/                 frontend existente, CSS Modules e cliente API
```

Grafo real: identificar → verificar registro de agentes → recuperar → gerar → validar referências → terminar; assuntos não suportados seguem saída controlada sem chamar um agente inexistente. Para adicionar um agente, inclua configuração/prompt no registro, amplie o roteador com testes e ingira documentos aprovados do domínio apropriado. Rotas e persistência não precisam ser reescritas. Não há microsserviços, filas ou outro framework de agentes.

Uploads usam identificadores aleatórios, nomes sanitizados, conteúdo validado, arquivos privados sem pasta pública e autorização em todas as operações. A extração PDF roda em subprocesso com limite de tempo, páginas, texto, memória e CPU no Linux. TXT/Markdown devem ser UTF-8. Não há execução de conteúdo. Anexos nunca entram no corpus compartilhado.

Logs JSON registram IDs de correlação, duração, agente, número de trechos e tipo de erro, sem mensagens completas, documentos ou credenciais. O health básico não indica que banco/modelos estejam prontos: use `/ready` autenticado. Não há criação automática de tabelas ao iniciar.

Limitações: validação de grounding é básica (IDs existentes, citações por parágrafo, números e identificação do material fictício), não uma prova de suporte semântico ou proteção absoluta contra prompt injection. O texto é exibido como texto React, sem HTML do modelo. Antes de uso corporativo, validar corpus, limiares, qualidade em português, políticas de retenção, quotas/rate limits, backups, papel SQL restrito e infraestrutura HTTPS. Supabase real e teclado virtual em dispositivo dependem de validação no ambiente correspondente.

Documentação consultada: [Ollama chat](https://docs.ollama.com/api/chat), [embeddings](https://docs.ollama.com/api/embed), [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming), [Supabase JWT](https://supabase.com/docs/guides/auth/jwts), [Qwen Instruct](https://ollama.com/library/qwen3:4b-instruct).
