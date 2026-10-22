# Contrato de avaliação 2.0.0 — proposta técnica

Este contrato é aditivo e aguarda aceitação humana. Não substitui o dataset 1.0.0, seu schema, seus critérios ou os scores já publicados.

- `contract.json` vincula explicitamente os seis assuntos de Folha Ponto e o fluxo estruturado de OP-03. Informar um ID em texto não representa uma seleção. O contrato de ações continua exigindo o escopo `education:contacts` e o estágio válido.
- `scenario-inputs.json` é entrada do runner real, sem fatos esperados. Deve ser usado em execução suplementar identificada, separada da bateria comparável de 76 perguntas originais.
- As orientações de OP-01/02/04 e os contatos de OP-03 têm proveniência de configuração operacional, com arquivo, SHA-256, origem e status reais. Não se exige um PDF fictício no novo canal. O avaliador histórico continua exibindo suas incompatibilidades de citação.
- Fontes documentais são vinculadas por ID de runtime, versão exata, hash documental e hash/ID de chunk. Isso identifica a fonte efetivamente utilizada; não estabelece equivalência com `snapshot-local-v1`. Todas as aprovações institucionais permanecem pendentes.
- O aviso de validação local é observado em metadados de fonte e tratado pela interface existente (`src/components/Chat.tsx`, `validation_only`). A inspeção do código não comprova que o aviso foi renderizado e visto: essa verificação visual fica pendente para o revisor. O critério lexical histórico que exige aviso no corpo continua preservado.
- O relatório do contrato 2.0 mede somente observações técnicas de entrada, proveniência e identidade de fonte. Não produz aprovação semântica nem converte um score histórico em outro.
- As decisões humanas abrangem fidelidade, completude, condições/exceções, citações, conflitos institucionais e restrições de acesso. Revisor, decisão, justificativa e data começam nulos. Aceitação do contrato não equivale à aprovação dos documentos.

A comparação principal usa as mesmas entradas do baseline `rag-real-183dfe28d96b`; os sete cenários suplementares demonstram o contrato novo com entradas explícitas. Resultados de cenários diferentes não devem ser somados como se fossem uma melhora do modelo sob entradas idênticas.
