# Contratos de entrada, proveniência e avaliação — Sprint 2

## Entradas explícitas e comparação histórica

O dataset 1.0.0 permanece inalterado. A execução `sprint2-fixes-verified-full` envia as mesmas perguntas, turnos e códigos de cartão do dataset original. Não infere o assunto pelos fatos ou fontes esperados.

FP-05, FP-11, FP-13, FP-14, FP-15 e FP-16 pressupõem Folha Ponto, mas não enviam esse assunto no contrato original. `scenario-inputs.json` declara uma seleção explícita de `topic_id=folha_ponto`, equivalente à escolha de assunto pelo usuário. É uma execução suplementar distinta, não substitui o histórico nem a execução comparável de 76 casos.

## Seleção estruturada de instrutor

Texto como “Selecionei instructor-11” não é uma ação de seleção. O cliente precisa abrir o fluxo, enviar `instructor_known` e então `instructor_select` com `instructor_id`. A API valida o estágio, a existência do instrutor e o escopo `education:contacts`. O identificador escrito em texto não confirma identidade nem autoriza a seleção.

O cenário suplementar OP-03 executa esse fluxo real antes da pergunta. Contato ausente não é inventado: o serviço informa a ausência e fornece somente os contatos educacionais configurados. Os contatos locais permanecem pendentes de validação institucional.

## Orientações operacionais

Portais e contatos provêm de `backend/app/support/operational_guidance.json`. A conversa registra em `support_state.operational_provenance` o arquivo, SHA-256 dos bytes reais, origem, status de validação e intenção. Essa informação aparece também nos estados finais brutos da avaliação. A consulta de conversa já expõe `support_state` pelo contrato existente; não houve alteração do frontend.

Essa proveniência não vira uma referência de PDF. As fontes documentais continuam representadas por chunks efetivamente recuperados. O avaliador canônico continua exigindo as referências originais: a incompatibilidade de citação operacional permanece visível e é relatada separadamente. Nenhuma fonte ou versão esperada foi fabricada para satisfazê-lo.

Em comparações entre Conecta Jovem e canais documentais, o modelo recebe a subpergunta documental e passa pela validação de grounding existente. Após essa validação, o serviço agrega a orientação operacional configurada e um aviso explícito de revisão, sem afirmar precedência ou vigência institucional. Se não houver resposta documental válida, não apresenta uma comparação documental inventada.

## Avisos de vigência

Para Folha Ponto, o contrato atual apresenta `validation_only` e demais metadados nas fontes; o prompt orienta que o aviso de vigência seja exibido na interface, sem exigir parágrafo adicional. O critério lexical do dataset exige esse aviso dentro da resposta. A divergência continua contabilizada; não houve mudança no prompt, na interface ou no critério para eliminar a falha.

Para VT, o formatador já inclui “vigência não confirmada” no texto e preserva os avisos de revisão do registro. Um aviso de revisão não prova resolução do conflito nem aprovação institucional.

## Versões e aprovação semântica

`snapshot-local-v1` continua diferente de `folha-ponto-local-v1` e `vt-segunda-via-local-v1`. As métricas estritas usam as versões reais. A métrica suplementar por localização ignora versão apenas para diagnóstico; não estabelece equivalência de snapshots.

Testes de roteamento, presença de fonte, contexto e critérios lexicais são observações automáticas. Todos os casos sem falha observável continuam inconclusivos até revisão humana; nenhum recebe aprovação semântica automática.

## Retomada

O runner grava um checkpoint atômico por caso. Repetir o comando com a mesma saída ignora casos concluídos somente se a assinatura de código, dataset, configuração, inventário documental e contrato suplementar for idêntica. Mudança da assinatura exige um novo diretório. A execução é sequencial; os turnos anteriores são enviados aos serviços reais.
