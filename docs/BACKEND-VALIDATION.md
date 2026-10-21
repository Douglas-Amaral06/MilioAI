# MilioAI — validação da primeira integração

Data: 20/10/2026, America/Sao_Paulo. Ambiente local Windows, Docker Desktop e Ollama 0.40.6. Nenhum deploy externo ou recurso Supabase foi criado.

## Resultado observado

O fluxo real React → FastAPI → LangGraph → RH Frequência → busca pgvector → Ollama → resposta SSE com fonte → PostgreSQL foi executado com sucesso. O material foi exclusivamente `backend/fixtures/frequency-test.md`, explicitamente fictício, aprovado pelo CLI e isolado no escopo `test`.

Pergunta: “No documento fictício de teste, qual o prazo para enviar atestado após retornar?”

O modelo respondeu com **3 dias úteis após o retorno**, declarou que o material não possui validade institucional e citou o trecho recuperado. A resposta não foi hardcoded: veio de `qwen3:4b-instruct` pelo `/api/chat` real. O diagnóstico isolado terminou com `done_reason=stop` e 46 tokens em uma execução. Os embeddings retornaram 768 dimensões reais. A ingestão persistiu dois trechos.

A primeira tentativa com `qwen3:4b` falhou por gerar análise e atingir o limite de tokens; também foram testados `think:false`, `/no_think` e o campo de raciocínio separado. Nenhuma dessas tentativas foi registrada como sucesso. A variante Instruct foi baixada e validada, preservando o modelo original instalado.

## Verificações executadas

- `npm run typecheck`, `npm run lint`, `npm run build`: passaram.
- `npm test`: sete testes do estado/armazenamento legado passaram.
- Pytest com `RUN_DB_TESTS=1` e `RUN_LIVE_TESTS=1`: **24 testes passaram**, sem skips nessa execução conjunta.
- Ruff: verificação dos fontes, migrations, testes e scripts.
- Mypy: passou em 31 arquivos da aplicação.
- `alembic upgrade head`: executado no PostgreSQL local novo, habilitando `vector`.
- `alembic check`: nenhuma operação de atualização pendente detectada.
- Ingestão administrativa real: documento fictício aprovado, dois chunks, embeddings de 768 dimensões.
- Edge/Playwright: **PASS**, console sem erros. Seleção real de arquivo pelo botão `+`, upload privado, remoção antes de enviar, persistência do anexo, resposta progressiva, fontes expansíveis e recarga.
- Navegador: renomeação e exclusão com confirmação; preservação da leitura de mensagens antigas; histórico longo com rolagem própria; cabeçalho/composer visíveis.
- Viewports: 1440×900, 1366×768, 390×844, 320×568 e 390×400. Sem rolagem vertical do documento. Capturas desktop e mobile inspecionadas visualmente.
- Desconexão real: o navegador abriu uma requisição SSE, recebeu o início e abortou a conexão. A resposta persistida mudou para `cancelled`, sem conteúdo parcial concluído.
- Erro real de conexão ao modelo: endpoint local sem serviço retornou `ModelError`, sem resposta artificial.

Testes de PostgreSQL verificaram CRUD, persistência, isolamento entre proprietários, escopos documentais, aprovação, domínio, versão da base, compatibilidade dos embeddings e limiar de similaridade. Testes criptográficos verificaram assinatura RSA, expiração, emissor e audiência, inclusive autenticação de dois sujeitos distintos com isolamento de conversas. Mocks foram usados apenas em testes isolados, nunca na aplicação executada.

Os primeiros testes do navegador precisaram de ajustes de sincronização para aguardar remoção assíncrona, capturar SSE sem a limitação intermitente do CDP do Edge e selecionar a conversa ativa entre títulos iguais. A execução final passou; os ajustes não mascaram falhas de aplicação.

## Arquivos e decisões

Criados: `backend/` com aplicação modular, Dockerfile, lock de dependências, migration Alembic, documentos fictícios, testes e scripts; `docker-compose.yml`; `.env.example`; `scripts/init-local.ps1`; cliente HTTP/auth em `src/api/client.ts`; formulário de login `src/components/SignIn.tsx`; este relatório.

Modificados: `src/hooks/useWorkspace.ts`, contratos em `src/types.ts`, `App`, `Chat`, `Composer`, `Sidebar` e estilos associados; `vite.config.ts`, `package.json`/lock (tipos Node para o proxy), `index.html`, `.gitignore`, README e teste de navegador. O design Demà, fonte local Space Grotesk, paleta e estrutura fixa foram preservados.

PostgreSQL é o histórico único; LangGraph não mantém um checkpointer paralelo. SSE e envio normal compartilham o mesmo serviço transacional. Fontes persistem snapshots dos trechos citados e seus IDs, versão e localização. UUIDs não são pedidos ao modelo: rótulos F1/F2 são resolvidos exclusivamente contra os chunks recuperados.

Busca exata pgvector no corpus inicial, com filtros de autorização materializados antes da distância. Modelo e dimensão variáveis são filtrados explicitamente; trocar modelo/prefixos exige nova versão e reingestão. Sem ANN desnecessário nesta entrega.

Autenticação local está explicitamente habilitada no `.env` gerado, restrita ao desenvolvimento e protegida por token aleatório injetado apenas pelo proxy local. Não é uma autenticação corporativa já provisionada. JWT corporativo é validado com JWKS assimétrico. Escopos são concedidos administrativamente no servidor.

Uploads reais ficam em volume privado persistente; nomes originais são sanitizados e os caminhos usam apenas identificadores aleatórios. PDF é analisado em subprocesso com limites; não há OCR, execução de arquivo nem ingestão automática de anexos no corpus institucional.

## Versões principais

PostgreSQL 17.11, extensão pgvector 0.8.7, Python 3.12 (container), FastAPI 0.151.0, Pydantic 2.14.1, SQLAlchemy 2.0.55, Alembic 1.20.0, psycopg 3.3.6, pgvector Python 0.5.1, LangGraph 1.2.16, HTTPX 0.28.1, PyJWT 2.15.1, pypdf 6.21.1, Uvicorn 0.54.0, Pytest 9.1.1, Ruff 0.17.1 e Mypy 1.20.2. Todas as dependências Python resolvidas estão em `backend/requirements.lock`; frontend em `package-lock.json`.

## Limites e pendências explícitas

- Supabase real não foi configurado nem testado com um projeto externo; README descreve issuer/JWKS, Email OTP, banco hospedado e concessão de escopos. Não há senhas próprias ou bypass de produção.
- O modo local compartilha uma identidade e serve apenas para validação local. Acesso corporativo exige configuração externa e escopos autorizados.
- A base usada é fictícia; não existem normas oficiais fornecidas. Não usar suas orientações como política real.
- Anexos são armazenados e exibidos como anexos, mas não interpretados pela IA.
- Grounding verifica existência das citações, identificação de teste, números e parágrafos citados; não prova suporte semântico completo nem imunidade à injeção de instruções. A qualidade precisa de avaliação com corpus autorizado antes de uso institucional.
- Não foi validado teclado virtual em um dispositivo físico. A redução de viewport foi testada no navegador.
- Rascunhos por conversa ficam em memória. O localStorage antigo permanece intacto e separado; não houve migração silenciosa.
- Produção ainda exige HTTPS/proxy, papel SQL restrito, proteção das tabelas Supabase contra acesso público, CSP, backups, quotas, limites de requisições e políticas de retenção/limpeza de arquivos órfãos.
- Só RH Frequência está implementado. Novos agentes precisam de domínio, prompt/políticas, documentos aprovados e testes de roteamento/isolamento; rotas e persistência são reutilizáveis.

## Conferência manual

Abra o endereço local do Vite. Crie uma conversa, faça a pergunta de teste acima, expanda a fonte e recarregue. Anexe um TXT fictício pelo `+`, remova-o, anexe novamente e envie com uma pergunta. Confira o aviso honesto de que o anexo foi armazenado sem interpretação pela IA. Pergunte por vale-transporte: a saída deve limitar o domínio suportado, sem inventar outro agente.

Consulte `/api/v1/ready` autenticado para banco e disponibilidade dos modelos. Testes de erro não desligaram o Ollama instalado: utilizaram conexão local sem serviço para simular indisponibilidade real sem afetar outros aplicativos.
