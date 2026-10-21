# Qualidade e governança do RAG — revisão offline

Este pacote prepara avaliação documental e análise determinística de exports locais. Não importa a aplicação, não executa modelos, não inicia serviços e não faz requisições. Requer apenas Python 3.10 ou superior, sem instalação de dependências.

Execute na raiz `MilioAI/MilioAI`:

```powershell
python docs/rag-quality/quality.py validate
python -m unittest discover -s docs/rag-quality/tests -q
```

## Artefatos

| Arquivo                       | Uso                                                                           |
| ----------------------------- | ----------------------------------------------------------------------------- |
| document_registry.json        | Inventário canônico, proveniência, aprovação, validade, escopos e hashes      |
| validation_registry.csv       | Visão derivada para revisão humana                                            |
| evidence_catalog.json         | 50 evidências resumidas com localização e hash do excerto                     |
| rag_eval_dataset.jsonl        | 76 casos de ground truth provisório, critérios e contexto                     |
| card_coverage.json            | Cobertura individual dos 33 cartões de VT, 24 na página 1 e 9 na página 2     |
| conflicts.json / conflicts.md | 9 pendências, sem resolução automática                                        |
| evaluation_schema.json        | Contrato de dados e exports; subconjunto autocontido validado pela ferramenta |
| results_template.json         | Template vazio, não representa execução                                       |
| evaluation_report.md          | Resultado da validação estrutural e limitações                                |
| EXPORT.md                     | Contrato para uma execução futura exportada                                   |

O conjunto contém 20 casos de folha ponto, 47 de VT, 5 operacionais e 4 de governança. Inclui 8 continuações, 2 mudanças de contexto, 8 ausências de informação, 3 ambiguidades, 3 conflitos e 4 verificações de autorização. Os 33 códigos distintos de VT possuem casos associados; quantidade de casos não é medida de precisão.

## Revisão institucional

Todos os documentos permanecem pendentes e com vigência não verificada. Datas de aprovação, revisão, início/fim de vigência e responsáveis desconhecidos permanecem nulos. A data de inspeção técnica não é uma data de aprovação. Nenhum documento foi autorizado para produção por este trabalho.

Os PDFs originais não estavam disponíveis. Folha ponto e VT foram conferidos em renderizações locais previamente existentes; VT também tem extrações locais. O hash de uma imagem, excerto ou chunk não comprova o hash do PDF original. O catálogo registra essa diferença e as evidências são resumos/excertos, não transcrições integrais. Os arquivos derivados em `tmp/` podem não acompanhar a distribuição: o validador avisa se faltarem; isso reduz a possibilidade de reconferência visual. Não há alegação de autenticidade ou vigência dos originais.

Para aprovar uma fonte, o responsável institucional deve obter e conferir o original, registrar hash e localização, esclarecer conflitos, confirmar escopo/versão/vigência, informar o revisor e a data reais e revisar os casos associados. Não invente datas ou responsáveis para satisfazer o validador. O inventário de instrutores e contatos registra apenas IDs e contagens; não republica o diretório pessoal.

Após editar os JSONs canônicos, atualize as visões e gere um novo template:

```powershell
python docs/rag-quality/quality.py render-views
python docs/rag-quality/quality.py validate
python docs/rag-quality/quality.py template --output docs/rag-quality/results_template.json
```

O template deve ser regenerado quando mudar dataset, evidências, inventário, conflitos ou cobertura. Resultados antigos não podem ser comparados silenciosamente a outra revisão: o avaliador rejeita hashes divergentes.

## Indicadores e limites

O avaliador calcula hit@k, recall@k, MRR@k, correspondência de documento/cartão, cobertura lexical de fatos, precisão/completude de citações e correspondência de rastros de contexto/comportamento/autorização. Médias incluem somente casos observados e aplicáveis, com denominadores explícitos; dados não registrados produzem nulos. Uma recuperação observada e vazia é falha de recuperação, não ausência de observação.

Critérios lexicais não verificam significado, negação ou fidelidade documental. Menções a alegações proibidas geram alertas para revisão, inclusive quando uma resposta as nega corretamente. Os rastros de comportamento/contexto são declarações do exportador. Não existe juiz LLM, nota geral de precisão ou aprovação automática. O relatório exige revisão humana e não declara ausência de alucinação.

O bloqueio de fontes corporativas considera aprovação, vigência, escopo, allowlist, original/hash e conflitos graves pendentes, incluindo fontes recuperadas além de k. Um resultado pode acertar o trecho esperado e falhar na autorização. Esse bloqueio é diagnóstico deste pacote, sem alteração do pipeline da aplicação.
