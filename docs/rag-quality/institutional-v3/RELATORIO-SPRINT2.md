# MilioAI — evolução institucional da Sprint 2

Data: 22/10/2026. Implementação incremental, com FastAPI, React, LangGraph, Ollama e PostgreSQL/pgvector preservados. A validação foi realizada em cópia do código e no banco isolado `milioai_sprint2_institutional_20261022`. A aplicação em execução não foi reiniciada e seu banco não foi migrado por esta entrega.

## 1. Arquivos criados e modificados

O inventário completo, com hashes antes/depois, está em `change-manifest.json`. O ZIP contém os arquivos alterados e as novas evidências; o backup contém as versões anteriores dos arquivos existentes. O patch é fornecido para revisão de código.

Principais arquivos:

- Novos: `backend/app/support/{contacts,exact,grounding,knowledge}.py`, `institutional_contacts.json`, `institutional_knowledge.json` e `link_policy.json`.
- Backend integrado: `agents/rh_frequency.py`, `llm/ollama.py`, `orchestration/graph.py`, `support/context.py`, `support/operational.py`, `support/operational_guidance.json`, `messages/service.py`, `api/schemas.py` e `db/models.py`.
- Migração: `backend/migrations/versions/0005_institutional_contacts.py`.
- Frontend: `InstitutionalContacts.tsx`, `MessageContent.tsx`, `safeLink.ts`, `Chat.tsx`, `types.ts`, `api/remote.ts` e `hooks/useWorkspace.ts`.
- Testes novos de confiabilidade institucional e renderização; testes existentes ajustados ao novo protocolo de seleção e à representação estruturada dos contatos.
- Executor real: `backend/scripts/evaluate_institutional_v3.py`; contrato aditivo `docs/rag-quality/contracts/3.0.0`; evidências em `docs/rag-quality/institutional-v3`.

## 2. Base de conhecimento

Foram adicionadas quatro anotações documentais com identificador, domínio, assunto, texto, fonte, página, seção, versão, hash, fatos estruturados, condições, exceções, contatos, restrições, validação e campos de aprovação nulos. O vínculo exige a versão e o hash calculado do conteúdo recuperado; uma anotação não cria autorização nem substitui o filtro de acesso do RAG.

Os registros de conhecimento e de configuração operacional permanecem separados. O diretório de instrutores, as linhas por código de Vale-Transporte e o inventário documental foram preservados. O chunk da regra de CURSO já continha a condição e a exceção: não houve alteração do chunking, reindexação ou migração da base documental. Apenas a composição de trechos para resposta evita separar contato e condição e retira títulos de seção da orientação exibida.

## 3. Contatos e governança

| Contato | Finalidade | Telefone | E-mail |
|---|---|---|---|
| Time Educacional | Curso, identificação de instrutores e orientação educacional | +55 11 99803-0631 | educacional.sp@renapsi.org.br |
| RH Jovem — Frequência | Folha Ponto, preenchimento, envio, prazo e frequência | +55 11 97080-6028 | frequência.sp@renapsi.org.br |

Os dados estão centralizados em `institutional_contacts.json`. A migração do contato educacional registra o hash da configuração anterior. Cada registro tem domínios, finalidades, escopos, origem, versão e status. Ambos continuam pendentes de validação institucional e de disponibilidade/titularidade WhatsApp. São bloqueados fora do ambiente de desenvolvimento enquanto estiverem pendentes. Frequência também exige fonte documental recuperada compatível e escopo `local_review`; Educacional mantém `education:contacts`. Não houve modificação da autenticação ou concessão de novos escopos.

O endereço acentuado foi preservado exatamente. Seu `mailto` permanece desabilitado: forma técnica aceita, suporte SMTPUTF8 e endereço vigente dependem de confirmação institucional. Não foi enviado e-mail nem mensagem WhatsApp para testar os canais.

## 4. Construção e renderização de wa.me

O backend valida o número internacional com dígitos e constrói `https://wa.me/` + `phone_digits`. Confere também a consistência com o número formatado. Retorna identificação, equipe, domínio, canal, URL, validação, disponibilidade e proveniência. Os destinos são:

- Educacional: `https://wa.me/5511998030631`.
- Frequência: `https://wa.me/5511970806028`.

Os contatos são enviados por evento SSE e persistidos na mensagem. O React usa o componente existente de mensagem, com os mesmos estilos Demà, e apresenta “WhatsApp do Educacional” ou “WhatsApp da Frequência” com nome acessível. O destino deve corresponder integralmente ao número estruturado; consultas, prefixos enganosos e alterações de dígitos são recusados. Links wa.me livres no Markdown gerado não são promovidos a destinos confiáveis. Outros links seguem a política central de domínios; instrutores mantêm seus e-mails autorizados. Não há mensagens pré-preenchidas com dados pessoais.

## 5. Proteção de valores exatos

Quando há números, contatos ou URLs, o modelo seleciona identificadores de trechos existentes; o backend projeta o conteúdo da fonte. A regra condicional de CURSO também tem uma representação estruturada vinculada à fonte. Contatos são resolvidos pelo backend, sem digitação de telefone pelo LLM.

Antes da liberação, são comparadas entidades completas: telefone, e-mail, URL, data, valor monetário e número com unidade. Prazos ordinais por extenso e marcadores relativos também recebem controles. Alterações são rejeitadas; não há correção aproximada, troca cega de dígitos nem criação de valores ausentes. Os controles existentes de citações e números foram mantidos.

## 6. Instruções do agente

As políticas globais reforçam fonte autorizada, modalidade, condições, objetividade, ausência de informação e separação de domínios. A seleção recebe apenas opções existentes. O avaliador de suficiência recebe fatos estruturados vinculados ao hash recuperado e exemplos sintéticos, sem telefones ou respostas institucionais codificados no prompt. As classificações `partial` e `none` continuam conservadoras e não são promovidas automaticamente.

## 7. Verificador semântico

O fluxo combina validação de entidades, verificação de regras/condições e julgamento semântico. Cada afirmação é associada às próprias citações. Trechos literais mantêm seu contexto completo no verificador. Proibição invertida, obrigação indevida, negação deslocada, ação ausente, prazo alterado, condição/exceção omitida e regra estruturada invertida podem vetar deterministicamente a resposta, mesmo se o modelo a aprovar.

O julgamento semântico continua habilitado e pode rejeitar uma projeção literal. Falha, incerteza, contradição ou ausência de suporte levam ao fallback existente. Não se trata de um provador universal de linguagem natural: as regras determinísticas cobrem as famílias implementadas e o modelo continua responsável pela avaliação semântica residual. Aprovação humana permanece separada.

## 8. FP-07 e FP-13 com integração real

Foram executadas quatro paráfrases por caso, com duas repetições, na bateria final registrada como `critical-run5`. FastAPI, LangGraph, embeddings, pgvector, seleção, grounding, persistência e recarregamento de histórico foram reais.

| Caso | Resultado |
|---|---|
| FP-13 | 8/8 aprovações técnicas: telefone e wa.me corretos, ajuda antes do prazo final, e-mail acentuado sem mailto, persistência confirmada. |
| FP-07 | 8/8 respostas preservaram a regra documental de manter CURSO; 4 classificadas `answered` e 4 `partial`. As quatro parciais não foram aprovadas pelo contrato técnico. |
| Total do contrato crítico | 12/16 aprovações técnicas. Nenhuma aprovação humana preenchida. |

As quatro parciais são as duas repetições de “Faltei no curso, coloco FALTA?” e “Posso trocar CURSO por FALTA?”. O avaliador continua conservador quanto à suficiência; as respostas e seus status foram preservados. A execução durou aproximadamente 64 segundos, abaixo do limite de 600 segundos. Não foi repetida a bateria histórica de 76 casos.

## 9. Controles adversariais

O teste real inicial encontrou um falso positivo: “Entregue o documento amanhã” contra uma fonte que apenas descrevia sua finalidade. Essa observação foi preservada. Após incorporar validações de ação e prazo ausentes, a bateria real terminou com **18/18 controles adversariais e positivos corretos**. Os testes determinísticos também usam um modelo simulado que aprovaria tudo, comprovando que ele não pode superar o veto das validações.

## 10. Regressões e integração

- Backend Linux com PostgreSQL habilitado: **179 testes aprovados**; 29 testes live antigos não foram executados nessa suíte. Evidência JUnit e log incluídos.
- Frontend: **43 testes aprovados**, build de produção e lint de `src` aprovados. Os testes verificam renderização HTML, acessibilidade dos links e destinos manipulados; não foi realizada inspeção visual de navegador.
- Verificação real adicional: continuidade conversacional, Educacional com instrutor desconhecido, duas intenções com contatos distintos, segunda via SPTrans e conflito PDF/Conecta Jovem. Os cinco fluxos foram observados com respostas HTTP 201 e conteúdos preservados.
- Na integração adicional, foi corrigido o agrupamento que antes absorvia o pedido do Educacional dentro da intenção Folha Ponto. Quando o usuário já declara desconhecer o instrutor, o fluxo existente passa diretamente ao contato educacional, mantendo a seleção individual autorizada nos demais casos.
- A migração 0005 foi aplicada somente no banco isolado. Repetir `alembic upgrade head` não reaplicou alterações. Nenhum documento foi reindexado.
- A suíte ampliada Windows teve uma limitação de subprocessos/loop assíncrono no teste de PDF; a suíte final equivalente passou em Linux. O lint global do repositório também aponta um erro preexistente em `docs/rag-quality/audits/2026-10-21/.work/build_csv.mjs` (`console`); esse artefato histórico foi preservado. O mypy global apresenta pendências preexistentes; as quatro novas unidades de suporte passaram na verificação direcionada.

## 11. Revisão humana

A fila original de 26 casos permanece intacta. O suplemento referencia FP-07, acrescenta as evidências de FP-13 e destaca contatos, inversões, condições, valores, vigência e conflito de canais. Todos os campos de aprovação humana/institucional permanecem nulos ou pendentes. O inventário já registrava a ausência dos PDFs originais; as anotações derivadas não corrigem essa ausência nem comprovam equivalência entre versões.

O conflito entre PDF e Conecta Jovem continua registrado e foi apresentado sem escolher precedência. Disponibilidade WhatsApp, titularidade, e-mail de Frequência e vigência documental dependem da instituição.

## 12. Decisão sobre a Sprint 2 e aplicação

A implementação fornece evidências técnicas para revisão: contatos determinísticos, FP-13 estável, ausência de inversões nos controles executados e regressões aprovadas. **A Sprint 2 não foi declarada encerrada**: permanecem quatro classificações parciais de FP-07, revisão humana e validações institucionais.

Os hashes dos relatórios históricos, contratos anteriores, fila humana, inventário e conflitos são comparados em `historical-integrity.json`. Não houve alteração de métricas históricas, PDFs, autenticação ou política de aprovação.

Para executar a nova versão no ambiente local, é necessário aplicar a migração 0005 ao banco do ambiente escolhido e reconstruir/reiniciar seus serviços conforme o procedimento existente. O banco de testes foi mantido para auditoria; nenhuma limpeza ou exclusão foi realizada sobre o banco em uso. O pacote inclui rollback do código por backup; a reversão da migração elimina somente a nova coluna de contatos, portanto deve ser avaliada antes de descartar contatos persistidos.
