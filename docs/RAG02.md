# RAG 02 — atendimento guiado e documento fornecido

20/10/2026 · America/Sao_Paulo. Entrega local, sem deploy remoto ou serviços pagos.

## Arquitetura

Foi reutilizada a aplicação FastAPI única, o frontend React aprovado, o banco PostgreSQL 17.11/pgvector 0.8.7 e o agente `rh_frequency`. Catálogo configurável no backend; PostgreSQL é a fonte de verdade de conversas, mensagens e seleção de assunto. Não há segundo histórico em LangGraph ou catálogo duplicado no frontend.

Grafo real: validar contexto/identificadores → selecionar domínio e agente → recuperar trechos autorizados → avaliar suficiência documental com Ollama → gerar resposta → validar referências → persistir conclusão. Sem agente compatível ou pergunta incompreensível, há saída controlada sem criar um especialista fictício. Falhas de modelo, embeddings ou banco permanecem erros técnicos, distintos da ausência de conhecimento.

O roteamento guiado utiliza o tópico validado, sem classificação por LLM. Perguntas livres usam regras pequenas e contexto persistido; uma mudança explícita de assunto prevalece sobre o tópico anterior. O histórico ajuda a resolver referências, mas apenas os trechos da consulta atual fundamentam políticas. O contexto é limitado e isolado por usuário/conversa.

## Catálogo único

`GET /api/v1/support/topics`, autenticado. Oito assuntos e 29 perguntas habilitadas:

| Assunto                               | Identificador             | Perguntas | Agente previsto          |
| ------------------------------------- | ------------------------- | --------: | ------------------------ |
| Folha Ponto                           | folha_ponto               |         7 | rh_frequency             |
| Atestados                             | atestados                 |         4 | rh_frequency             |
| Benefício Vale-Transporte             | vale_transporte           |         4 | indisponível             |
| Benefício Vale-Refeição / Alimentação | vale_refeicao_alimentacao |         4 | indisponível             |
| Salário                               | salario                   |         4 | indisponível             |
| Falta no Curso                        | falta_curso               |         3 | rh_frequency             |
| Falta no Trabalho                     | falta_trabalho            |         3 | rh_frequency             |
| Outros                                | outros                    |         0 | identificação pelo texto |

Tópicos têm ID, título, descrição opcional, domínio, agente previsto, ordenação, habilitação e escopos necessários. Perguntas têm IDs estáveis, tópico, texto, ordem e habilitação. O catálogo não contém respostas ou evidências documentais.

`POST /conversations/{id}/messages` e `/stream` aceitam `topic_id` + `question_id`; o servidor resolve o texto canônico e rejeita adulteração ou associação inválida. Texto livre usa `content`. `PATCH /conversations/{id}/topic` persiste a seleção, inclusive o retorno ao menu. Mensagens guardam tópico e pergunta originais. O grafo revalida o contexto na sua fronteira.

## Interface

A saudação curta dá acesso a linhas compactas de assuntos, em duas colunas no desktop e uma no mobile. Selecionar um tópico abre as perguntas e a ação **Voltar aos assuntos**. Selecionar uma pergunta envia a requisição real imediatamente. Após a resposta, **Fazer outra pergunta** reabre o menu do assunto. **Outros** convida a escrever no composer, sem perguntas obrigatórias.

Foram preservados sidebar, busca, histórico, anexos, tipografia Space Grotesk, grafismos, paleta Demà, CSS Modules, cabeçalho/composer fixos e rolagem interna. Fontes aparecem apenas por resposta, com documento, seção, página, versão e identificação de validação local. Não há botão global de fontes.

Cliques repetidos em uma pergunta são bloqueados por referência síncrona antes da chamada HTTP. UUID de requisição, bloqueio transacional da conversa e índice de processamento também impedem duplicação no backend. A inicialização agora aguarda o histórico antes de permitir criar/selecionar assunto, evitando uma condição de corrida encontrada durante os testes.

## PDF e ingestão

Fonte utilizada: `ORIENTAÇÕES PARA PREENCHIMENTO DA FOLHA PONTO.pdf`, fornecido pelo usuário em Downloads. O nome com `(1)` citado no escopo não foi presumido como outro documento; o usuário confirmou expressamente este arquivo.

SHA-256: `3de571b6232dcc6130db18fe2b5700c2b98eefc12219595706a66e11b69b115f`.

Duas páginas lidas integralmente, texto extraído com pypdf e renderização Poppler inspecionada. O documento possui oito seções numeradas; foram gerados nove trechos, incluindo o título/prefácio inicial. Regras, condições e consequências de uma seção permanecem juntas; a exceção de curso não foi cortada da sua justificativa. Não existe quantidade fixa de chunks nem respostas extraídas como tabela de FAQs.

Cada trecho tem ID, documento, seção, página, índice, conteúdo, hash e vetor. Domínio, aprovação/status, versão, escopo, perfil de embeddings e sinalização `validation_only` estão no documento relacionado. A migration 0002 é aditiva e preservou a base anterior.

A indexação administrativa exige `--approve`; a execução feita utilizou `--local-review --scope local_review`. `approved` significa autorização para o escopo local configurado, não confirmação de vigência institucional. O sinalizador `validation_only` exclui o PDF da recuperação fora do desenvolvimento. Não há rota pública de aprovação. Documentos pendentes ou revogados são filtrados antes da distância vetorial.

O comando repetido retornou **Already indexed**, sem novos chunks para o mesmo hash/versão/escopo/modelo/dimensão/perfil. Uma primeira indexação de avaliação foi preservada em outro perfil, sem mistura entre espaços. Nenhum documento ou conversa existente foi apagado.

## Embeddings e recuperação

Ollama `nomic-embed-text-v2-moe:latest`, 768 dimensões reais. Prefixos corretos `search_query: ` e `search_document: `, incluindo o espaço final. A representação para embeddings inclui nome/contexto do documento, seção e texto; a evidência exibida ao usuário continua sendo o conteúdo original. A identidade do perfil inclui modelo, dimensão, prefixos e versão da estratégia de chunking (`sections-v3-contextual`).

Busca exata pgvector, até três candidatos, limiar local de distância cosseno 0,55. Filtros de domínio, escopo, aprovação, status, versão, modelo, dimensão, perfil e restrição de validação são materializados **antes** de calcular distância. Os retornos incluem score e metadados para diagnóstico; embeddings de consultas não são persistidos.

| Avaliação em seis perguntas curadas                  | Hit Rate@3 | Recall@3 | MRR@3 |
| ---------------------------------------------------- | ---------: | -------: | ----: |
| Inicial, trechos sem contexto adicional, limiar 0,45 |       0,50 |     0,50 |  0,50 |
| Contexto documental nos embeddings, limiar 0,45      |      0,833 |    0,833 | 0,833 |
| Contexto documental e limiar local 0,55              |       1,00 |     1,00 |  1,00 |

Isso significa **seis acertos em seis perguntas conhecidas deste PDF**, não acurácia geral de 100%. Cada caso tem uma seção/página esperada, por isso Recall e Hit Rate coincidem nesta amostra. Prazo, horários, curso, assinaturas, envio e atraso tiveram a seção esperada em primeiro lugar na avaliação final. Assinaturas teve score aproximado de 0,488, mostrando por que o limiar anterior a excluía. O limiar precisa ser reavaliado com outros documentos e perguntas negativas.

Resultados reproduzíveis em `rag02-retrieval-baseline.json`, `rag02-retrieval-contextual.json`, `rag02-retrieval.json` e no comando `python -m app.rag.evaluate`. A calibração mais permissiva em 0,60 também foi registrada, mas não adotada.

## Geração e limites documentais

`qwen3:4b-instruct` avalia primeiro a cobertura em JSON estruturado (`sufficient`, `partial`, `none`) e as referências sustentadoras. Nenhuma resposta institucional é armazenada no catálogo. Sem cobertura, há fallback; erro de conexão é indisponibilidade técnica. Depois da geração, o backend valida citações, IDs reais, números, parágrafos citados e sinalização de material fictício quando for o corpus legado.

Exemplos reais observados:

- Prazo: resposta sobre **segundo dia útil do mês**, fonte **2. Periodicidade e Prazo**, página 1.
- Horários: orientação de registrar horários corretos, sem usar horário britânico, fonte **3. Como preencher corretamente**, página 1.
- Curso: manter o preenchimento como **CURSO** para evitar desconto duplicado, fonte **3. Como preencher corretamente**, página 1.
- Assinaturas: Aprendiz e assinatura/carimbo do Gestor/Mentor, fonte **5. Assinaturas obrigatórias**, página 2.
- Continuação “E se eu atrasar?”: consequências descritas como **possíveis**, fonte **2. Periodicidade e Prazo**, página 1.
- Prazo de atestado: ausência de informação suficiente; a base fictícia antiga não contaminou a resposta.
- Pagamento de VT, salário e férias: assunto sem informações disponíveis/agente adequado; nenhuma data, meio de pagamento ou procedimento foi fabricado.

O estado documental não é inferido da existência de uma FAQ. Escopos não vêm de IDs enviados pelo navegador. O histórico de outro usuário nunca é consultado. Instruções presentes nos documentos são dados, não comandos privilegiados; as regras de geração permanecem no prompt de sistema. Esses controles reduzem riscos, mas não provam ausência de alucinação ou imunidade à injeção de instruções.

## Testes e problemas encontrados

A suíte conjunta passou em **41 testes Python**, incluindo PostgreSQL/pgvector e modelos reais. O frontend passou em **10 testes**, TypeScript, lint e build. Ruff, Mypy e `alembic check` foram executados. A avaliação de recuperação foi separada da de geração.

Foram testados IDs adulterados, permissões de tópicos, isolamento documental, status pendente/revogado, exclusão de `validation_only` em produção, modelos/perfis incompatíveis, duplicação de envio concorrente, persistência do tópico e roteamento livre/guiado. Os testes reais cobrem o PDF, continuidade, troca de assunto e fallbacks. O teste no Edge terminou em **PASS**, sem erros de console: catálogo, persistência da seleção, envio por ID, três cliques produzindo uma requisição, resposta SSE real, fonte de prazo e de assinaturas, recarga, continuidade, troca de assunto, Outros, fallback de férias e upload/remoção reais. Foram testadas 1440×900, 1366×768, 390×844, 320×568 e 390×400, com composer visível e sem rolagem global. As capturas desktop/mobile e fontes foram inspecionadas visualmente. O servidor Vite temporário de teste foi encerrado, sem reinstalar dependências.

Falhas reais durante o desenvolvimento: recuperação inicial insuficiente; classificação documental excessivamente conservadora; combinação indevida da regra geral de falta com a exceção de curso em uma saída do modelo; repetição do prazo em vez de responder à continuação; bloqueio de uma resposta por aviso separado sem citação; corrida entre carregamento inicial e nova conversa. Foram ajustados representação/limiar, instruções de suficiência, preservação de exceções, papéis do histórico, prompt da pergunta atual e inicialização. Nenhuma dessas execuções foi tratada como sucesso. A validação precisa continuar com amostras maiores.

## Arquivos principais

Criados: `backend/app/support/catalog.py`, `support/context.py`, `rag/chunking.py`, `rag/evaluate.py`, migration `0002_guided_support.py`, testes guiados/integração/avaliação real, fixture compartilhada de testes, `src/components/SupportMenu.tsx` e testes, este relatório e os resultados quantitativos.

Modificados: contratos API, rotas, modelos SQLAlchemy, serviço de mensagens, configuração/autorização local, cliente Ollama, grafo, prompt RH, ingestão/recuperação; `src/api/client.ts`, hook, tipos, App, Chat, Sidebar e estilos; teste de navegador, `.env.example`, `.gitignore` e README. Dependências novas não foram necessárias.

## Executar e evoluir

O README contém os comandos locais e o mount somente para leitura do PDF. O corpus ativo é `folha-ponto-local-v1`; o antigo `test-v1` fica separado. Não rode `npm ci` com Vite aberto. O backend usa o container Python 3.12; não depende do Python 3.15 do host.

Pendências: confirmar vigência e escopos institucionais antes de disponibilizar o documento em produção; configurar/testar Supabase real; ampliar avaliação com perguntas negativas, paráfrases e documentos adicionais; revisar rate limits, quotas, retenção e papel SQL de produção. O roteador livre é intencionalmente simples e tem cobertura limitada. Não foi validado teclado virtual em dispositivo físico. Anexos continuam armazenados sem interpretação pela IA.

Novos agentes precisam de domínio, responsabilidade, prompt e documentação aprovada, com testes de isolamento. O catálogo já informa o agente previsto; não será necessário reescrever rotas ou histórico. CMS, filas, outros bancos vetoriais e agentes fictícios não foram introduzidos.

Referências técnicas: [Ollama embeddings](https://docs.ollama.com/api/embed), [modelo Nomic](https://ollama.com/library/nomic-embed-text-v2-moe), [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).
