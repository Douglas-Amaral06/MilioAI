# Homologação do orquestrador — 21/10/2026

## Causa-raiz

O fluxo existente selecionava uma única rota para a mensagem inteira. `is_transport()` rejeitava VT ao encontrar termos como “folha”, e a seleção de contexto escolhia apenas um assunto. Assim, a solicitação composta podia chegar inteira ao agente de frequência, com evidências de apenas esse domínio. A geração emitia `delta` antes de `validate_references()`. Um parágrafo longo sem citação levantava `ValueError`, convertido em `AppError`; a execução descartava toda a resposta. A validação anterior também aceitava citações formais sem comprovar sustentação semântica e verificava números contra fontes agrupadas.

Saudações tinham um problema distinto: não existia um fluxo social. Pela inspeção do código anterior, “Oi” podia seguir para classificação operacional e depois esclarecimento por incompreensibilidade. O log fornecido comprova falha de grounding da pergunta composta; não comprova uma exceção em saudações.

## Implementação incremental

- `backend/app/support/intents.py`: reconhecimento de mensagens exclusivamente sociais e planejamento conservador de até três solicitações. Fronteiras interrogativas e mudança explícita de assunto são necessárias; “SPTrans e quanto custa” permanece uma solicitação. Misturas sem fronteira clara pedem esclarecimento.
- `backend/app/orchestration/graph.py`: entrada social, execução sequencial dos fluxos existentes, orçamento dividido entre intenções, validação de permissões por tópico, isolamento de histórico por assunto e composição sem nova geração. Os mesmos filtros de recuperação documental e de cartão continuam aplicados.
- `backend/app/support/context.py`: SPTrans, Bilhete Único e cartão TOP reconhecidos como assunto explícito, mesmo após outro tópico selecionado.
- `backend/app/support/transport.py`: identificadores explícitos de cartões têm prioridade sobre exclusões genéricas. Mensagens compostas passam antes pelo planejador.
- `backend/app/agents/rh_frequency.py`: mantém `validate_references()`, identifica índices dos parágrafos sem referências, exige citações também em afirmações curtas e verifica números exclusivamente nas referências do respectivo parágrafo. Apenas uma lista fechada de títulos sem afirmações fica dispensada de citação.
- `backend/app/llm/ollama.py`: verificação semântica com saída JSON estrita; cada parágrafo recebe somente seus trechos citados. Falhas, truncamento e respostas fora do contrato não aprovam conteúdo. VT continua sendo projetado deterministicamente dos campos da linha recuperada, preservando seu fluxo individual.
- `backend/app/messages/service.py`: registra o resultado real da execução; respostas parciais e ausência de evidência não são classificadas como sucesso no log final.
- `backend/app/main.py`: permite serializar metadados de intenção, domínio, etapa, correção e resultado no formato JSON existente.

## Grounding, SSE e falhas parciais

A resposta documental gerada fica em memória. Só após validação estrutural e semântica o grafo publica `delta` e `sources`. Há no máximo uma regeneração corretiva, se restarem pelo menos cinco segundos no orçamento. A nova resposta passa pelas mesmas validações. Persistindo a falha, publica-se apenas o texto confiável de informação insuficiente, sem fontes. Nenhuma citação é acrescentada automaticamente.

Cada subfluxo é consumido privadamente. A composição publica somente resultados concluídos; citações F1/F2 são substituídas pelos IDs imutáveis dos respectivos chunks, evitando colisões entre domínios. Uma falha independente mantém as outras partes aprovadas e acrescenta uma indicação explícita de que aquele assunto não pôde ser concluído.

O contrato existente já suporta `status=complete` e `outcome=partial`. `complete` indica que o processamento e a persistência terminaram; `partial` indica que o atendimento não foi integralmente concluído. Não houve migração de banco nem novo status. Se nenhuma intenção fornecer resposta válida, o resultado é `no_evidence`. Uma única mensagem de assistente é persistida. Cancelamento e idempotência continuam cobertos pela integração.

O buffering aumenta o tempo até o primeiro texto, pois inclui geração e verificação. Nas mensagens compostas, a publicação aguarda as subintenções. A escolha prioriza impedir exposição de conteúdo rejeitado. Os eventos SSE `start`, `delta`, `sources`, `done` e `error` mantêm seus formatos. As chamadas ao Ollama são sequenciais; não há aumento de concorrência por mensagem.

## Testes

Executados em cópia temporária do backend, em `/tmp/orchestrator-review` no contêiner de desenvolvimento, com Python 3.12, PostgreSQL existente e sem substituir a API em execução:

```sh
RUN_DB_TESTS=1 python -m pytest -q
python -m ruff check app tests scripts/check_orchestrator_live.py
PYTHONPATH=/tmp/orchestrator-review python scripts/check_orchestrator_live.py
```

A suíte unitária/de integração passou com **94 testes**. Os 28 testes live existentes permanecem condicionados às respectivas variáveis de ambiente; parte deles inclui ingestão/reindexação e não foi habilitada nesta correção. A validação real exigida foi executada separadamente pelo script acima, sem mocks e sem ingestão.

| Casos solicitados | Evidência automatizada |
| --- | --- |
| 1–3: Oi, Bom dia, Obrigado | testes sociais sem sessão ou chamadas de modelo; smoke real |
| 4–8: saudação com VT, fluxos individuais, pergunta composta e taxa | planejamento, execução composta e smoke real |
| 9: três intenções | execução de Folha Ponto + SPTrans + salário, preservando partes disponíveis |
| 10: ambiguidade | mistura sem fronteiras pede esclarecimento; testes operacionais existentes para documento genérico |
| 11–13: sem citação, fonte inventada, afirmação sem suporte | validação estrutural, números por referência local e rejeição semântica |
| 14–16: correção, fallback e streaming rejeitado | eventos contêm exclusivamente a resposta corrigida ou fallback |
| 17–18: falha parcial e domínios | composição com erro de VT, IDs separados e persistência em PostgreSQL |
| 19: mudança de assunto | contexto explícito SPTrans ↔ Folha Ponto e regressões existentes |
| 20: permissões e filtros | tópico restrito preserva outra intenção; consulta recebe escopos/domínio; testes existentes de ACL e filtros documentais |

Arquivos de teste: `backend/tests/test_orchestration_reliability.py`, `backend/tests/test_reliability_integration.py` e ajuste do mock em `backend/tests/test_integration.py` para o novo método de verificação. O script reproduzível é `backend/scripts/check_orchestrator_live.py`. Respostas, IDs, domínios consultados no PostgreSQL, códigos e durações estão em `docs/orchestrator-live-results.json`.

## Evidências reais

Ambiente: `development`, modelo `qwen3:4b-instruct`, escopo de desenvolvimento já configurado `local_review`. Não foram alteradas aprovações, documentos, permissões ou configuração de produção.

“Oi”, “Bom dia” e “Obrigado” retornaram `social`, sem fontes. Folha Ponto individual retornou o prazo até o segundo dia útil, com fonte de `rh_frequency`. A mensagem “Oi, como solicito a segunda via do SPTrans?” retornou `answered`, código 89 e fonte de `beneficios.vale_transporte.segunda_via`.

As duas mensagens compostas do pedido foram respondidas com seções de Folha Ponto e VT e dois IDs distintos. Na rodada final, a mensagem original com duas perguntas levou aproximadamente 33 segundos. SPTrans preservou quem solicita, quem paga, taxa em tarifas, dinheiro e procedimento documentado, com ressalva de vigência. O smoke compara o texto de todos os eventos `delta` com a resposta final e exige igualdade.

## Limitações e riscos restantes

O planejador é deliberadamente conservador, baseado em fronteiras de solicitações e assuntos explícitos; não é um extrator semântico universal. Formulações compostas sem separação clara podem pedir esclarecimento. Perguntas do mesmo assunto permanecem juntas.

A verificação semântica usa o modelo local: reduz o risco de aceitar citação irrelevante, mas não constitui prova formal e pode produzir falsos positivos ou negativos. Falhas de verificação geram fallback. O custo adicional é uma chamada de verificação por resposta documental e, eventualmente, uma geração corretiva. Solicitações lentas podem consumir o orçamento de uma intenção e resultar em resposta parcial.

O smoke real verifica o grafo com os serviços reais e os eventos customizados. Persistência e contrato HTTP/SSE são cobertos pelos testes de integração com PostgreSQL, usando modelos controlados. A API em execução não foi reiniciada nem recebeu deploy; o código alterado está no workspace, pronto para revisão e implantação pelo fluxo habitual.
