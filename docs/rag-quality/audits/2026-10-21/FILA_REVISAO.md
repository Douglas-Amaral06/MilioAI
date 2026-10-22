# Amostra priorizada para revisão humana

Os dez primeiros são os casos destacados no relatório principal. A fila tem 24 registros e cobre todas as causas principais efetivamente observadas, sem produzir exemplos artificiais de timeout ou falha de grounding. Resultado e resposta originais devem ser mantidos.

| Ordem | Caso | Tema principal para revisão |
| ---: | --- | --- |
| 1 | CONFLICT-01 | PDF versus Conecta: contraste omitido e pendência documental |
| 2 | VT-10398 | Nome de cartão municipal não identificado |
| 3 | CTX-04 | Cartão ativo perdido após encaminhamento operacional |
| 4 | FP-03 | Prazo confundido com serviço de envio |
| 5 | FP-10 | Recuperação de seções sem a orientação de foto/legibilidade |
| 6 | OP-03 | Seleção de instrutor por texto versus ação; contato ausente |
| 7 | OP-04 | Validação de contatos confundida com fornecimento de contatos |
| 8 | VT-155 | Taxas por via, ordinais e contato incompleto |
| 9 | FP-09 | Perspectiva do assistente versus orientação ao usuário |
| 10 | AUTH-01 | Limite da política em desenvolvimento versus teste corporativo |
| 11 | FP-14 | Assunto pressuposto sem histórico/tópico enviado |
| 12 | FP-04 | Recuperação sobre prazo em vez de horários reais |
| 13 | FP-06 | Busca vazia sobre falta e falta justificada |
| 14 | OP-01 | Conteúdo pertinente sem referência de configuração exigida |
| 15 | OP-02 | Proveniência, ressalva e singular/plural de atestado |
| 16 | NEG-02 | Saldo confundido com entrega de documento |
| 17 | NEG-06 | Custo sem cartão exige esclarecimento, mas recebe fallback |
| 18 | VT-15779 | Endereço ausente na fonte; pergunta cai em documento genérico |
| 19 | VT-503 | Divergência Jovem versus qualquer pessoa, explicitada sem arbitragem |
| 20 | VT-9156 | Canal ausente reconhecido por paráfrase rejeitada pelo léxico |
| 21 | CONFLICT-02 | Número 0800 incompleto reconhecido por paráfrase |
| 22 | AUTH-03 | Recusa explícita e limite do rótulo operacional/aliases |
| 23 | CTX-06 | Continuação sobre BO perde o cartão selecionado |
| 24 | FP-02 | Prazo citado, primeira pessoa e aviso em outro canal |

## Protocolo de decisão

1. Abrir o caso em [CASOS.md](CASOS.md) e conferir o JSON bruto vinculado. Comparar contexto realmente enviado, estado, pergunta e resposta integral.
2. Identificar o trecho efetivamente recuperado e a fonte citada. Não usar a evidência esperada como se tivesse sido recuperada. Conferir ID, versão, página, seção e cartão.
3. Comparar cada afirmação com o trecho: número/unidade, condição, responsável, exceção, negação, temporalidade e completude. Separar omissão de uma afirmação contraditória.
4. Anotar se a divergência pertence ao sistema, à entrada/critério do caso, à fonte institucional ou ao contrato entre esses componentes. Uma paráfrase lexicalmente rejeitada exige justificativa textual, não promoção automática.
5. Para FP-14 e OP-03, decidir primeiro o cenário de entrada. Não corrigir retroativamente o JSON bruto ou substituir a resposta por uma nova execução.
6. Registrar revisor, data, evidência literal e decisão em um arquivo de revisão separado. Aprovar uma resposta não aprova a autenticidade/vigência do documento nem autoriza uso em produção.

O arquivo [human-review-queue.json](human-review-queue.json) mantém `reviewer=null` e `decision=pendente`. Não foram preenchidas decisões ou aprovações em nome de um revisor humano.
