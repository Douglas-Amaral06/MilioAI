# Export de uma execução futura

Este pacote apenas lê um arquivo local; a execução do sistema avaliado deve ocorrer separadamente e ter autorização própria. Não execute serviços ou modelos para validar este pacote. Não derive respostas reais das respostas esperadas.

1. Valide os dados e gere um template vazio com `python docs/rag-quality/quality.py template --output tmp/rag-export.json`.
2. Na execução futura, envie cada pergunta e seus turnos/contexto do dataset ao sistema avaliado. Capture a resposta efetivamente produzida e os rastros de recuperação, citação e contexto, mantendo a ordem original da recuperação. Não preencha um rastro com a resposta esperada.
3. Mantenha os hashes e a versão do template. Informe `run_kind` como `real`, um identificador de execução rastreável e `executed_at` com a data/hora real e fuso ISO 8601. Essa classificação é uma declaração do exportador; não é prova criptográfica de execução.
4. Preencha `results` conforme `$defs.result` em `evaluation_schema.json`. Use os `test_id` existentes, sem duplicatas. Casos ausentes serão relatados explicitamente.
5. Avalie o arquivo já exportado:

```powershell
python docs/rag-quality/quality.py evaluate tmp/rag-export.json --k 3 --output tmp/rag-report.json
```

Cada resultado exige `test_id`, `retrieval_status`, `retrieved`, `citation_status`, `citations`, `generation_status`, `answer`, `behavior`, `context_status` e `context`. Os status são `observed` ou `not_recorded`. Para dados não registrados use listas vazias e valores nulos, sem inventar evidência. Uma recuperação observada vazia significa zero resultados. `behavior` admite `answer`, `clarify`, `fallback`, `surface_conflict` ou nulo; registre somente uma classificação observada/revisada, não a esperada. O contexto exige `domain` e `benefit_code`, nulos quando desconhecidos.

As referências em `retrieved` e `citations` exigem `document_id`, `source_version`, `section_or_row`, `page` e `benefit_code`. Campos opcionais são `chunk_id`, `runtime_document_id`, `document_hash` e `chunk_hash`. Consulte o schema para tipos, nulos e limites. Citações são rastros explícitos, não inferidas pelo avaliador a partir do texto da resposta.

Os IDs do inventário são aliases de avaliação. Os UUIDs reais de documentos/chunks devem ficar em `runtime_document_id`/`chunk_id`. Faça uma correspondência verificável por fonte, versão, página, seção e código do benefício; não converta apenas por título parecido. As referências locais do frontend `folha-ponto-local-v1`/`vt-segunda-via-local-v1` não substituem essa correspondência. A versão `snapshot-local-v1` só descreve os derivados disponíveis e não deve ser atribuída automaticamente a documentos de produção.

O `sha256` exposto pelo chunk da recuperação existente não é o hash do PDF. Registre-o como `chunk_hash`; deixe `document_hash` nulo se não houver hash do original. Sem o original/hash e sem aprovação institucional, a autorização corporativa deve falhar. Não copie o hash de uma imagem ou do excerto para preencher essa lacuna.

O avaliador rejeita templates, exports sintéticos pela CLI de avaliação real, IDs desconhecidos/duplicados e hashes desatualizados. Resultados parciais são aceitos e a cobertura faltante aparece no relatório. Indicadores não observáveis permanecem nulos, com denominadores próprios. O relatório não contém os textos completos das respostas; mantenha o export de entrada sob os controles adequados, especialmente se contiver dados pessoais.

Revise manualmente as respostas contra os documentos, verificando negação, condições, valores, datas, cartão e continuidade. Os indicadores lexicais e os rastros de comportamento não substituem essa revisão nem autorizam uma fonte para produção.
