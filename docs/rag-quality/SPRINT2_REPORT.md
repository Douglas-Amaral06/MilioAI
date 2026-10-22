# Sprint 2 — avaliação real do RAG

Data: **21/10/2026**. Execução principal: **09:59:26–10:01:30, America/Sao_Paulo**. Run: `rag-real-371771d521c9` — os hashes estão em [manifest.json](runs/sprint2-full/manifest.json).

## Resultado e classificação

Foram executados **76/76 casos**, com **86 turnos reais**: 76 perguntas avaliadas e 10 turnos anteriores reproduzidos. Nenhuma resposta esperada foi usada para preencher respostas ou rastros. A amostra inicial de oito casos foi executada separadamente e passou nos controles de integridade antes da bateria completa.

| Domínio | Executados | Aprovados semanticamente | Reprovados | Inconclusivos | Não executados |
| --- | ---: | ---: | ---: | ---: | ---: |
| Folha Ponto | 20 | 0 | 13 | 7 | 0 |
| Vale-Transporte | 47 | 0 | 28 | 19 | 0 |
| Operacional | 5 | 0 | 4 | 1 | 0 |
| Governança | 4 | 0 | 0 | 4 | 0 |
| **Total** | **76** | **0** | **45** | **31** | **0** |

“Reprovado” significa falha observável contra o caso: comportamento, localização documental, citação, contexto ou a perspectiva incorreta apontada pelo usuário em FP-09. Não significa necessariamente afirmação falsa: quatro casos operacionais falham porque o contrato atual não expõe a proveniência documental esperada pelo dataset. Uma recusa segura pode falhar por não atender a uma pergunta respondível.

Dos checks estritamente automáticos, **14 passaram, 44 falharam e 18 ficaram inconclusivos**. O feedback do usuário sobre FP-09 acrescenta uma reprovação ao resultado final, sem alterar a resposta bruta nem transformar essa observação em uma revisão institucional. Nenhum caso foi aprovado semanticamente apenas por correspondência lexical. Os demais 31 continuam pendentes de revisão humana.

Os detalhes por caso estão em [case-verdicts.csv](runs/sprint2-full/case-verdicts.csv) e [summary.json](runs/sprint2-full/summary.json).

## Metodologia e integridade

O runner usa o backend atual em processo isolado, PostgreSQL/pgvector e Ollama reais. Autentica o token existente pelo endpoint FastAPI `/api/v1/me`, sem substituir dependências de autenticação. Em seguida usa os mesmos serviços `prepare()`/`execute()` e o LangGraph da aplicação, com o principal autenticado e escopos **reduzidos** aos do caso. Não há concessão de permissões ou alteração de usuários. Os escopos necessários, inclusive `education:contacts`, já estavam disponíveis para o usuário de desenvolvimento.

Cada caso tem conversa própria persistida. Turnos anteriores são realmente enviados ao sistema; o histórico inclui as respostas geradas por ele. Quando necessário, a seleção de cartão usa as ações existentes, sem preencher um cartão a partir da resposta esperada. Nesta bateria, o contexto necessário foi estabelecido pelos turnos anteriores. Não foi enviado um tópico derivado da resposta esperada para facilitar o roteamento de perguntas autônomas.

Os hooks de avaliação registram consultas, filtros, ordem dos candidatos, chunks, seleção posterior pelo assessor, atualizações do grafo, fontes finais, eventos SSE, resultados e durações. Eles observam e encaminham as mesmas chamadas; não substituem respostas ou recuperação. A execução é sequencial, com timeout existente de 120 segundos por turno. Há checkpoints atômicos por caso e recusa de retomada se código, inventário, configuração ou dataset mudarem.

Os **76 casos** passaram na conferência de pergunta exata, igualdade entre os deltas e o texto final, fontes presentes na recuperação e resolução dos marcadores de citação. Os eventos são capturados no serviço SSE em processo; não se trata de um teste de rede/proxy ou do frontend.

A retomada da execução concluída foi testada: **zero casos repetidos**, com apenas autenticação/inventário e sem novas gerações. Uma interrupção durante um caso permite repetir somente esse caso em outra conversa; os checkpoints concluídos não são repetidos. Não houve timeout nesta bateria.

## Correspondência de fontes e diferença de versões

O dataset identifica PDFs por aliases e usa `snapshot-local-v1`. O runtime efetivamente retornou `folha-ponto-local-v1` e `vt-segunda-via-local-v1`. Os exports preservam essas versões reais, os UUIDs e hashes observados; não atribuem a versão do snapshot aos documentos do banco.

A correspondência de aliases considera domínio e a referência de versão runtime já cadastrada no inventário, com conferência de página/seção/código. A auditoria vinculou as **12 localizações de Folha Ponto** e os **33 cartões de VT**. Os campos dos 33 registros de VT coincidem exatamente com a extração local cujo hash consta no pacote. Existem dois documentos runtime de Folha Ponto, com o mesmo hash de blob, que foram registrados separadamente e não removidos. Não foi usada apenas semelhança de título.

Os hashes de documento exportados foram conferidos contra os bytes efetivamente armazenados. `chunk_hash` continua separado de `document_hash`. Isso comprova os bytes locais observados, **não autenticidade institucional, equivalência entre versões ou vigência**. Os documentos continuam pendentes no inventário de governança, mesmo que o banco tenha uma flag técnica `approved` para revisão local.

Ver [document-crosswalk.json](runs/sprint2-full/document-crosswalk.json) e [crosswalk-validation.json](runs/sprint2-full/crosswalk-validation.json).

## Métricas

O avaliador original foi reutilizado sem modificar dataset, schema, inventário ou critérios. A CLI e a chamada importada produziram relatórios JSON semanticamente idênticos.

As métricas **estritas**, que exigem igualdade de versão, são Hit Rate@3 = **0**, Recall@3 = **0** e MRR@3 = **0**, com **64 casos aplicáveis**. Precisão/completude estrita de citações também é zero. Esses resultados incluem a incompatibilidade de versões: não devem ser apresentados como prova de que nenhuma fonte relevante foi encontrada.

Para diagnosticar o roteamento e a recuperação, foi calculado um indicador adicional por **alias + página + seção/cartão**, ignorando versão de maneira explícita. Ele não declara equivalência documental nem substitui o resultado estrito. As referências exportadas não foram alteradas para calculá-lo.

| Domínio | N documental | Hit Rate@3 por localização | Recall@3 por localização | MRR@3 por localização | Cobertura lexical de fatos | Completude de citação por localização |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Folha Ponto | 18 | 38,9% | 38,9% | 0,389 | 20,0% (20 casos) | 38,9% (18 casos) |
| Vale-Transporte | 42 | 40,5% | 40,5% | 0,405 | 35,1% (47 casos) | 40,5% (42 casos) |
| Operacional | Não aplicável à busca vetorial | — | — | — | 10,0% (5 casos) | 0% (4 casos) |
| Governança | Não aplicável | — | — | — | 0% (4 casos) | — |

No total documental, localização Hit/Recall@3 = **40,0%** e MRR@3 = **0,400**, sobre **60 casos**. Nos 33 casos individuais de cartão, apenas **10/33** recuperaram a linha esperada.

Outros indicadores observados:

- Correspondência de comportamento: **36/76 = 47,4%**. É igualdade entre rótulos de comportamento, não precisão semântica. Responder com uma ressalva explícita de revisão pode produzir `surface_conflict` onde o dataset espera `answer`; esses casos foram destinados à revisão, sem reprovação automática por esse motivo isolado.
- Fallback esperado: **7/9 = 77,8%**. Esclarecimento esperado: **1/3 = 33,3%**.
- Contexto completo: **19/44 = 43,2%** nos casos em que o avaliador aplica esse indicador, incluindo perguntas diretas com cartão. Correspondência de domínio: **28/44 = 63,6%**; cartão: **19/44 = 43,2%**.
- Continuidade nos **10 casos com `requires_context=true`**: **8/10 = 80,0%**. CTX-04 e CTX-06 perderam o atendimento específico do cartão.
- Cobertura lexical macro dos fatos obrigatórios: **27,6%**, sobre 76 respostas. Não mede fidelidade, negação correta ou ausência de alucinação.
- **24 respostas** apresentaram fontes. Todas as fontes finais pertencem aos chunks efetivamente recuperados; não foram observadas citações inventadas. A completude por localização, incluindo os quatro casos operacionais que exigem proveniência, é **37,5% em 64 casos**.
- Não houve alertas lexicais de alegações proibidas. A conclusão semântica correspondente continua **não avaliada**.

Os denominadores detalhados estão no [relatório do avaliador](runs/sprint2-full/quality-report.cli.json). A taxa estrita de autorização de fontes do pacote também é afetada por versões não registradas e allowlists específicas de cada caso; não deve ser interpretada como taxa de violação da autenticação do runtime.

## Recuperação, geração, grounding e citação

Houve **28 chamadas de recuperação nas perguntas principais** e 36 contando os turnos anteriores. Entre os **36 casos documentais sem a localização esperada**, **33 não chegaram à recuperação**. Os demais foram FP-04, FP-06 e FP-10:

- FP-04: foi recuperada a seção de prazo em vez da regra sobre horários iguais; houve fallback.
- FP-06: a busca retornou vazia; houve fallback.
- FP-10: foram recuperadas assinaturas, finalidade e responsabilidade, sem a orientação esperada sobre foto/legibilidade; houve fallback.

Os resultados finais foram: 24 `answered`, 23 `out_of_scope`, 14 `operational`, 10 `card_selection` e 5 `no_evidence`. Não houve exceções de recuperação, falhas de geração, timeouts ou eventos `grounding_failed`/`grounding_repair`. Isso descreve a bateria observada; não comprova robustez geral nem ausência de alucinação. Muitos casos retornaram cedo, antes de geração documental.

**40 casos** ficaram sem a citação/localização esperada: 36 documentais e quatro operacionais. Nos operacionais, a orientação vem de configuração confiável, mas o contrato atual não fornece o rastro documental exigido pelo dataset. Trata-se de uma lacuna de proveniência, sem evidência de fonte fabricada.

Os quatro casos de governança produziram fallback/recusa. AUTH-01 e AUTH-04 foram executados com a política documental de produção aplicada ao grafo **dentro do ambiente de desenvolvimento**, mantendo a autenticação de desenvolvimento. Eles não comprovam comportamento de um deployment corporativo. Como essas perguntas não chegaram à consulta documental, uma verificação SQL complementar, somente de leitura, confirmou: zero documentos de frequência sob filtro de produção; zero cartões sob filtro de produção; 33 cartões na revisão local; zero cartões sem escopo. Nenhum documento foi liberado para produção. Ver [governance-query-probe.json](runs/sprint2-full/governance-query-probe.json).

## Tempos

| Domínio | Média da pergunta | P50 | P95 | Máximo |
| --- | ---: | ---: | ---: | ---: |
| Folha Ponto | 2,278 s | 2,340 s | 5,082 s | 8,717 s |
| VT | 1,215 s | 0,328 s | 3,770 s | 4,157 s |
| Operacional | 0,289 s | 0,252 s | 0,437 s | 0,437 s |
| Governança | 0,130 s | 0,019 s | 0,244 s | 0,244 s |
| **Todos os 76** | **1,377 s** | **0,319 s** | **4,157 s** | **8,717 s** |

Incluindo a preparação do contexto de cada caso: média **1,616 s**, P50 **0,331 s**, P95 **5,411 s**, máximo **8,725 s**. Percentis usam nearest rank. A baixa latência agregada é influenciada por respostas antecipadas e fallbacks; não caracteriza o desempenho de respostas documentais bem-sucedidas em geral. Não há extrapolação de capacidade ou carga concorrente.

## Cinco principais problemas e prioridades

1. **P0 — reconhecimento incompleto de cartões e seus nomes alternativos.** Apenas 10 dos 33 casos individuais de VT atingiram a linha esperada. Há perguntas com nome suficiente para identificar o cartão que recebem seleção novamente ou vão para `documental`/`ambiguous_document`: VT-10398, VT-10420, VT-15504, VT-15508, VT-15779 e VT-3854 são exemplos. Revisar aliases a partir do diretório autorizado e a política de encaminhamento ao fluxo de VT, mantendo confirmação quando houver mais de um candidato. Não trocar fontes nem completar dados institucionais para compensar o roteamento.
2. **P0 — paráfrases documentais confundidas com serviço operacional ou assunto indisponível.** FP-03 pergunta “Até que dia...” e recebe o portal de envio sem prazo; FP-13 é encaminhado para contato educacional; outras formulações sem o termo literal “folha” retornam fora de escopo. CONFLICT-01 também vira apenas serviço de envio. Melhorar a distinção entre regra/prazo e acesso ao serviço, com regressões dessas formulações. Avaliar separadamente ranking e limiar de recuperação em FP-04/06/10; este conjunto não justifica reindexação automática.
3. **P1 — continuidade do cartão perdida em perguntas curtas.** CTX-04 (“Quem abre o pedido então?”) e CTX-06 (“Preciso de boletim de ocorrência?”) reabrem a seleção apesar do cartão previamente estabelecido. O gate de follow-up não cobre essas formulações e `operational_router()` reinicializa `vt_stage` antes de encaminhar novamente ao transporte. Ajustar essa transição preservando o cartão na continuação e mantendo a mudança explícita de assunto.
4. **P1 — incompatibilidade de proveniência entre dataset e runtime.** Os indicadores estritos ficam zerados por versão; a configuração operacional não expõe as referências esperadas. Registrar formalmente a correspondência de versões e um contrato de proveniência operacional, com aprovação por responsável quando cabível. Até lá, manter resultados estritos e os indicadores adicionais separados. O inventário não comprova aprovação institucional; obter originais, responsáveis, vigência e resolver os conflitos antes de autorização corporativa. Não renomear versões nem marcar documentos como aprovados para melhorar métricas.
5. **P1 — perspectiva da resposta e revisão semântica insuficiente.** FP-09 respondeu “Não, não posso assinar...”, como se a ação fosse do assistente. O usuário apontou o problema. Foi feita uma correção posterior, limitada à instrução de dirigir a orientação ao usuário, sem alterar regras institucionais. A validação real separada retornou “Você não pode assinar a folha de outra pessoa ou em branco [fonte:F1]”. O caso original permanece reprovado nesta bateria. Revisar também modalidade, negação, conflitos e completude das respostas aprovadas pelos checks lexicais; os indicadores automáticos não substituem essa tarefa.

## Mudanças, testes e reprodução

Arquivos novos: `backend/app/rag/evaluate_real.py`, `backend/scripts/evaluation_policy_probe.py`, `backend/tests/test_evaluate_real.py`, `backend/tests/test_perspective_live.py`, `docs/rag-quality/summarize_real.py` e `docs/rag-quality/tests/test_real_summary.py`. O prompt em `backend/app/agents/rh_frequency.py` recebeu a correção de perspectiva **depois** da execução dos 76 casos. As alterações da Sprint 1 já presentes no workspace foram preservadas.

Testes definitivos: **100 testes unitários/de integração passaram**, **39 testes do pacote offline passaram**, e **1 teste live pela API passou** para a correção de perspectiva. O export foi validado pelo schema e avaliado pela CLI original. As tentativas locais afetadas por permissões de temporários/cache foram repetidas com sucesso no contêiner e com cache desabilitado.

No runtime Python do backend, com as variáveis de desenvolvimento já configuradas:

```sh
python -m app.rag.evaluate_real --package ../docs/rag-quality --output /caminho/nova-execucao --sample
# Conferir a amostra antes de continuar no MESMO diretório e na MESMA versão do código.
python -m app.rag.evaluate_real --package ../docs/rag-quality --output /caminho/nova-execucao

# Reexportar somente observações já gravadas, sem chamadas de modelo ou banco:
python -m app.rag.evaluate_real --package ../docs/rag-quality --output /caminho/execucao --export-only
```

Na raiz do projeto:

```sh
python docs/rag-quality/quality.py evaluate docs/rag-quality/runs/sprint2-full/results.json --k 3 --output /caminho/relatorio.json
python docs/rag-quality/summarize_real.py docs/rag-quality/runs/sprint2-full
```

O diretório principal contém os 76 JSONs brutos em `cases/`, export, relatórios, logs, checkpoints, hashes e correspondências. O export inicial anterior às duas correções de leitura do adaptador foi preservado. `postprocessing-manifest.json` registra a reexportação, que não executou modelos. As versões do runner e do agente que geraram a bateria estão preservadas e conferem com o manifest. A alteração de prompt posterior faz a guarda de retomada recusar a mistura silenciosa de versões; para nova avaliação, usar outro diretório.

A regressão de perspectiva está em [runs/perspective-fp09](runs/perspective-fp09/results.json), separada da bateria. Os artefatos brutos podem conter excertos documentais e dados de configuração retornados ao usuário autorizado: devem permanecer sob os controles do workspace, sem publicação automática. Não foram alterados frontend, autenticação, regras institucionais, aprovações ou índices, nem apagados documentos institucionais ou volumes do PostgreSQL. A API em execução não recebeu deploy desta correção.
