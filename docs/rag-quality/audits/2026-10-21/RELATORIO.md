# Auditoria dos 76 resultados do RAG

**Data:** 21/10/2026. **Execução auditada:** `rag-real-371771d521c9`.

Foram comparados individualmente os 76 casos, suas perguntas/contextos, respostas, fatos e referências esperados, candidatos recuperados, fontes finais, transições do grafo e motivos da classificação. Os resultados **45 reprovados e 31 inconclusivos permanecem intactos**. Nenhum caso foi promovido. Não houve execução de modelos, consultas ao PostgreSQL ou alteração do LangGraph, do RAG, dos prompts ou dos critérios nesta auditoria.

## Conclusão principal

Os **45 reprovados não representam 45 erros factuais**. A classificação mistura falhas funcionais do atendimento, contratos não alinhados e entradas que pressupõem contexto não enviado. Nos registros analisados, não foi demonstrada uma **afirmação factual positiva que contradiga a evidência local**. Isso não comprova ausência de alucinação, nem aprova as respostas ou a vigência das fontes. Há omissões comprovadas, pedidos não atendidos e perda de estado.

Dos 45 reprovados, **36 têm falha funcional identificável no MilioAI**, **6 exigem esclarecer a entrada do dataset/runner**, e **3 dependem de um contrato entre avaliação e aplicação**. A contagem é por causa principal, sem contar novamente falta de citação ou contexto quando são consequência do mesmo problema.

O score estrito de recuperação/citação zerado decorre também de versões incompatíveis: `snapshot-local-v1` no dataset versus versões locais reais no runtime. Isso é uma restrição legítima da definição estrita, **não um erro de aritmética do avaliador**. Interpretar esse zero como “nenhum trecho pertinente foi encontrado” seria um erro de interpretação da avaliação. Não se deve renomear versões para corrigir o score.

## Distribuição das causas dos 45 reprovados

| Causa principal | Casos | Responsabilidade principal | O que a evidência demonstra |
| --- | ---: | --- | --- |
| Roteamento de intenção | 23 | MilioAI | Serviço, assunto ou resposta escolhidos não atendem ao pedido; não houve busca documental pertinente |
| Identificação do cartão | 7 | MilioAI | O fluxo chega a VT, mas pede novamente qual cartão apesar do nome municipal/operadora informado |
| Recuperação sem trecho pertinente | 3 | MilioAI | FP-04 e FP-10 recuperam seções inadequadas; FP-06 retorna zero candidatos |
| Estado do cartão perdido | 2 | MilioAI | CTX-04 e CTX-06 passam de cartão ativo para nova seleção, sem mudança solicitada |
| Perspectiva da resposta | 1 | MilioAI | FP-09 responde “não posso”, como se a ação fosse do assistente; a proibição documental não foi invertida |
| Assunto pressuposto sem contexto enviado | 6 | Dataset/runner | FP-05/11/13/14/15/16 não estabelecem folha ponto na pergunta, histórico ou tópico selecionado |
| Proveniência operacional sem contrato de citação | 2 | Compartilhada | OP-01/02 atendem ao conteúdo principal, mas a configuração operacional não é exposta como a fonte exigida pelo dataset |
| Seleção de instrutor não estabelecida | 1 | Compartilhada | OP-03 envia “Selecionei instructor-11” como texto, sem ação nem estado de seleção; a resposta não informa ausência de contato |
| **Total** | **45** | | |

**Categorias adicionais solicitadas:** não houve timeout, evento de falha de grounding ou fonte inventada demonstrados. As divergências documentais são fatores secundários, especialmente em CONFLICT-01 e VT-3854, e pendências visíveis em VT-503/155/9156 e CONFLICT-02. Não foram resolvidas por esta auditoria.

Os 36 casos anteriormente contabilizados como ausência da localização documental esperada se dividem em **33 sem chamada de busca** e **3 com busca sem o trecho pertinente**. Portanto, “fonte não recuperada” não permite concluir que o ranking vetorial falhou em 36 casos.

A falta de citação esperada aparece em **40 casos**: 36 documentais não atendidos e quatro operacionais. Não são 40 demonstrações de geração de parágrafos documentais sem suporte. Nos operacionais, OP-03 também falha em estabelecer/usar o instrutor e OP-04 responde à pergunta errada; a justificativa original “citação ausente” não descreve todo o problema.

## Por que os 31 ficaram inconclusivos

| Grupo principal | Casos | Explicação |
| --- | ---: | --- |
| Checks automáticos passaram, sem revisão humana | 14 | A regra do resumo exige revisão semântica; os acertos automáticos não geram aprovação |
| Aviso esperado no texto, entregue por outro canal | 6 | O prompt de execução manda deixar o aviso na interface; as fontes têm `validation_only=true` e o frontend contém o aviso na área de fontes |
| Limitação lexical ou diferença de taxonomia | 9 | Equivalências linguísticas e notas de revisão não coincidem com os aliases/rótulos aceitos |
| Limite de governança/ambiente | 2 | AUTH-01/04 exercitam política em desenvolvimento, sem comprovar autenticação ou deployment corporativo |
| **Total** | **31** | |

Os 14 casos do primeiro grupo são **VT-164, VT-7099, VT-182, VT-10771, VT-503, VT-89, VT-738, VT-472, CTX-01, CTX-02, CTX-05, CTX-08, NEG-01 e NEG-07**. São 12 controles com resposta documental/contexto e dois controles de fallback/esclarecimento. Permanecem inconclusivos; a auditoria não os aprova.

O grupo do aviso contém **FP-01, FP-02, FP-07, FP-08, FP-12 e CTX-07**. Seus fatos principais passaram lexicalmente e encontram correspondência nos trechos locais. O critério adicional exige que o texto diga que a vigência não foi confirmada. O prompt baseline, preservado em `execution-rh_frequency.py`, determina o contrário quanto ao canal: a interface já comunica a pendência. O frontend `Chat.tsx` confirma a existência do aviso dentro da área expansível de fontes. A auditoria não comprovou que o usuário abriu essa área nem que a comunicação visual seja suficiente; há um requisito de canal a decidir, não uma regra institucional a modificar.

Os nove casos lexicais/taxonômicos são **VT-155, VT-9156, CONFLICT-02, CTX-03, CTX-09, NEG-04, NEG-05, AUTH-02 e AUTH-03**. Em cada um, a análise individual explica a frase ou o rótulo que falhou. AUTH-01/04 continuam limitados pelo ambiente e também não explicam expressamente a política solicitada.

## Possíveis falsos negativos e pontos cegos

Esses achados são diagnósticos. **Nenhum critério foi alterado e nenhum score foi recalculado para melhorar o desempenho.**

1. **Versões das fontes:** as 24 respostas com citações têm localizações correspondentes, mas versões diferentes das registradas como snapshot. A equivalência de versões não foi estabelecida. O zero estrito deve permanecer; a limitação precisa acompanhar sua interpretação.
2. **Ordinais em VT-155:** a resposta distingue 11,80, 23,60 e 47,20 por 2ª, 3ª e 4ª vias. A normalização transforma os ordinais em `2a/3a/4a`, que não casam com `2/3/4`. É um falso negativo lexical candidato, não prova de taxa única incorreta.
3. **Paráfrases de ausência em VT-9156 e CONFLICT-02:** “não informa URL nem número” e “sem informar o número completo” não casam com “não informado”, “não consta” ou “incompleto”. O texto não inventa o contato ausente.
4. **Singular/plural em OP-02:** o critério exige `atestado`, mas a resposta contém `atestados`. A cobertura lexical cai apesar do conteúdo principal pertinente. A falta da referência operacional e do aviso explícito continua sendo outra questão, não eliminada por essa constatação.
5. **Recusas em NEG-04/05 e AUTH-02/03:** as formulações reais não aparecem nos aliases do critério. AUTH-03 recusa expressamente o acesso; não há divulgação de contatos sem escopo demonstrada.
6. **Taxonomia de conflito:** CTX-03/09, VT-155/9156 e CONFLICT-02 contêm resposta com nota de revisão. O rótulo `surface_conflict` difere de `answer`. O resumo anterior já tratava esse fator isolado como pendência de revisão, e não como reprovação eliminatória.
7. **Entradas subespecificadas:** FP-05/11/13/14/15/16 pressupõem folha ponto sem estabelecer esse assunto no cenário enviado. O runner preservou o texto do dataset, mas não enviou `topic` como seleção de interface. É preciso decidir se são testes de inferência autônoma ou de conversa contextual. Não se deve acrescentar contexto retroativamente aos registros.
8. **Proveniência de configuração versus recuperação vetorial:** OP-01/02 não usam busca vetorial. A resposta principal é pertinente, mas não há rastro no formato documental esperado. Decidir o contrato antes de tratar essa ausência como erro factual ou exigir um PDF inexistente.

Há também **falsos positivos potenciais** nos indicadores: OP-03 recebe correspondência de contexto porque a métrica só compara domínio/cartão; ela não verifica `selected_instructor_id`. OP-04 tem comportamento genérico `answer` compatível com o esperado, embora não responda sobre validação. Em **VT-15508, VT-15512, VT-15779, VT-200 e NEG-02**, o texto pergunta qual documento entregar, mas o exportador o rotula `answer` pelo outcome operacional genérico; a intenção registrada é `ambiguous_document`. FP-02 passa no fato de prazo apesar da perspectiva “Devo entregar minha folha”. Portanto, relaxar apenas os checks rígidos não resolveria os pontos cegos.

## Dez casos prioritários

| Ordem | Caso | Resultado preservado | Por que investigar | Decisão humana necessária |
| ---: | --- | --- | --- | --- |
| 1 | CONFLICT-01 | Reprovado | Compara PDF e Conecta, mas recebe somente portal de envio | Confirmar canais e o dever de expor a divergência sem declarar revogação |
| 2 | VT-10398 | Reprovado | Nome CIT Sumaré Urbano informado, mas sistema pede cartão novamente | Verificar se o nome identifica inequivocamente a linha 10398 no diretório autorizado |
| 3 | CTX-04 | Reprovado | Código 216 ativo deixa de ser usado após reset da etapa | Confirmar que a pergunta é continuação e auditar a transição de estado |
| 4 | FP-03 | Reprovado | “Até que dia” vira acesso ao serviço, sem prazo | Separar intenção de prazo e intenção de envio; validar o trecho de prazo |
| 5 | FP-10 | Reprovado | Busca retorna assinaturas/finalidade/responsabilidade, sem foto legível | Conferir pertinência da seção 6 e condições de recuperação |
| 6 | OP-03 | Reprovado | Texto de seleção não equivale a ação; resposta não informa e-mail ausente | Definir contrato de seleção textual/estruturada e comparar estado real |
| 7 | OP-04 | Reprovado | Pergunta sobre validação recebe contatos | Verificar omissão da resposta sobre vigência e contrato de proveniência; não presumir vazamento |
| 8 | VT-155 | Inconclusivo | Valores por via presentes, mas ordinais falham no léxico | Conferir a distinção das taxas e a pendência de telefone sem aprovar a fonte |
| 9 | FP-09 | Reprovado | “Não posso” atribui a ação ao assistente | Registrar inadequação de perspectiva separada de contradição institucional |
| 10 | AUTH-01 | Inconclusivo | Fallback em desenvolvimento não é teste de produção | Definir a evidência exigida para autenticação/deployment e para recusa explícita |

A fila completa contém **24 casos**, cobrindo todas as 12 classes principais observadas, com exemplos dos dois domínios documentais e dos controles operacionais/governança. Ver [FILA_REVISAO.md](FILA_REVISAO.md) e [human-review-queue.json](human-review-queue.json). Timeout e falha de grounding não têm ocorrência para amostrar; não foram inventados casos dessas categorias. FP-04/10 servem como controles de fallback sem evento de grounding, não como falhas de grounding.

## O que pertence ao avaliador e o que pertence ao MilioAI

**MilioAI:** os rastros sustentam problemas de roteamento, nomes de cartões, busca pertinente, continuidade e perspectiva. Há pedidos não atendidos mesmo quando as evidências locais existem. Omissão e fallback seguro não equivalem a erro factual afirmativo, mas são falhas de atendimento.

**Avaliador/dataset/runner:** requisitos de contexto não enviados, aliases lexicais estreitos, observação do aviso apenas no texto, taxonomia exclusiva `answer`/`surface_conflict`, contexto limitado a domínio/cartão e avaliação corporativa feita em desenvolvimento. O comparador estrito de versões está funcionando como definido; o alinhamento das referências e a interpretação do zero exigem decisão de governança, não uma alteração oportunista.

**Compartilhados:** a forma de citar configuração operacional e a representação de seleção de instrutor. Nos três casos com causa principal compartilhada, é prematuro atribuir toda a reprovação a geração ou ao avaliador.

**Documentação institucional:** a existência de versões locais, flags técnicas de aprovação e fontes com conteúdo não resolve vigência, autenticidade ou conflitos. A auditoria não arbitra valores, canais, contatos ou responsáveis e não aprova documentos para produção.

## Rastreabilidade e entregas

- [CSV dos 76 casos](AUDITORIA_76_CASOS.csv): ID, domínio, resultado, causa, evidência, ação, pergunta/resposta integral, fatos esperados, fontes, critérios não atendidos e prioridade. Os campos originais foram preservados separadamente das conclusões técnicas.
- [Comparação individual em Markdown](CASOS.md): todos os 76 casos com resposta, fatos, comparação, localização observada/esperada, motivo original e link ao JSON bruto.
- [Dados da auditoria](audit-data.json) e [prova de integridade](integrity.json).
- Fontes originais: [relatório da execução](../../SPRINT2_REPORT.md), [export](../../runs/sprint2-full/results.json), [resumo](../../runs/sprint2-full/summary.json), [avaliador](../../runs/sprint2-full/quality-report.json) e os 76 JSONs em `runs/sprint2-full/cases/`.

Os hashes de **146 arquivos protegidos** foram conferidos antes/depois: registros brutos, exports, dataset, critérios e código da aplicação permaneceram inalterados. O export inicial e o posterior têm as mesmas 76 respostas; as diferenças são apenas metadados de contexto/comportamento já documentadas na execução anterior. A regressão posterior de FP-09 foi mantida separada e não substitui o erro da bateria original.

Esta é uma auditoria técnica assistida por IA dos registros disponíveis, com um feedback específico do usuário em FP-09. Não substitui revisão semântica humana nem validação institucional. A fila permanece sem revisor e sem aprovações preenchidas. As recomendações são propostas para a próxima etapa; nenhuma correção do sistema ou mudança de regra foi executada aqui.
