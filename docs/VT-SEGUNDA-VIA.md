# RAG de segunda via do vale-transporte

## Documento e extração

As duas páginas e suas tabelas foram lidas integralmente e conferidas visualmente. A extração administrativa usa o pypdf já existente, sem dependências novas. São **33 linhas / 33 códigos únicos**, 24 na página 1 e 9 na página 2. Cada linha gera um chunk, mantendo UF, código, nome, solicitante, pagador, pagamento, taxa e procedimento integral. Quebras de linha e alinhamento de moeda são normalizados sem converter taxas ou corrigir o texto do documento. O procedimento do Eroles foi recuperado integralmente mesmo onde a extração por células não o reconhecia.

O extrator exige duas páginas e exatamente o conjunto de 33 códigos revisados; alterações de estrutura interrompem a ingestão para revisão. Não é um importador genérico de tabelas. As anotações de revisão correspondem a esta versão do PDF e devem ser revistas para outro documento.

## Persistência e recuperação

- Domínio: `beneficios.vale_transporte.segunda_via`.
- Versão independente: `VT_KB_VERSION`, padrão `vt-segunda-via-local-v1`.
- Modelo real: `nomic-embed-text-v2-moe:latest`, 768 dimensões; consultas usam o prefixo de busca já configurado.
- Perfil de extração/embedding: `vt-table-v1`; não substitui a versão/perfil do corpus Folha Ponto.
- Armazenamento: PDF original privado; PostgreSQL/pgvector com página, origem, versão, hash, escopo e campos estruturados em `attributes`.
- Migração aditiva `0004`: `benefit_code`, `attributes`, índice e unicidade de `(document_id, benefit_code)`; chunks antigos continuam com código nulo.
- Idempotência por hash do PDF, versão, escopo, modelo, dimensão e perfil; trava transacional impede reindexações concorrentes do mesmo espaço. A reexecução encontra o documento sem duplicar os 33 chunks ou gerar novamente os vetores.

A seleção pelo código é validada no backend. O código exato é filtrado **antes** da distância vetorial, junto de domínio, versão, perfil, modelo, dimensões, aprovação e escopos. O limiar semântico não pode substituir a operadora selecionada. Nenhum registro de outra operadora é usado como alternativa. Mais de uma fonte para o mesmo código é tratada como conflito, sem mesclar procedimentos. A listagem autenticada retorna somente código, nome e UF da base autorizada.

## LangGraph, modelo e continuidade

O grafo ganhou uma entrada para segunda via e um nó de atendimento, preservando os agentes anteriores. Intenções explícitas e a pergunta guiada existente no catálogo de Vale-Transporte abrem a lista. O classificador semântico existente também pode encaminhar para a nova intenção. Nomes inequívocos e códigos explícitos identificam cartões; nomes compartilhados, como BB Turismo, exigem seleção.

O estado `support_state` já persistido armazena `vt_stage` e `selected_card_code`. A conversa pode recarregar, trocar cartão e continuar perguntando sobre valor, taxa, documentos ou prazo sem perder a operadora. Outro assunto suspende esse contexto; perguntas explícitas sobre Folha Ponto, salário, atestados ou instrutores mantêm os fluxos anteriores. Um nome desconhecido não reutiliza silenciosamente o cartão anterior.

Para preservar rigorosamente valores, contatos e responsabilidades, a geração é extrativa: o Ollama lê a pergunta e o chunk exato e retorna um plano JSON restrito aos campos relevantes. O servidor monta a resposta usando os campos recuperados literalmente, com citações e links seguros. A seleção inicial apresenta o procedimento completo; acompanhamentos projetam os campos pertinentes. Não há paráfrase livre de taxas ou procedimentos. Falha do modelo retorna erro controlado, sem simular uma resposta de IA. As fontes continuam passando pela validação de referências existente.

Solicitante Empresa é destacado como responsabilidade da empresa. Valores em tarifas permanecem em tarifas; não são convertidos em reais. A resposta explicita vigência não confirmada e não preenche contatos, prazos ou documentos ausentes com dados externos.

## Frontend

`TransportCards` reutiliza a apresentação compacta e os estilos existentes: busca sem distinção de acentos, código/UF visíveis, botões de seleção por teclado e clique, lista de altura limitada e ação para trocar cartão. Procedimentos e taxas não aparecem na lista. Ações estruturadas seguem pelo endpoint de stream existente. O composer, a sidebar, o botão de anexos e o renderer seguro de Markdown foram preservados. Links HTTP/HTTPS e e-mail presentes no registro ficam clicáveis; domínio sem protocolo não ganha um protocolo inventado.

## Inconsistências e lacunas para revisão

- **3854 — Rápido D’Oeste:** coluna de taxa informa **6 tarifas**, enquanto o procedimento menciona **21,30**. Os dois dados permanecem; não foi escolhida uma correção nem feita conversão.
- **503 — SOU Diadema:** coluna Quem solicita informa **Jovem**, mas o procedimento permite solicitação por **qualquer pessoa**. A divergência é mostrada.
- **15779 — Bem Santana de Parnaíba:** menciona endereço abaixo, sem informar esse endereço na linha.
- **9156 — TOP:** menciona página de autoatendimento/chat e WhatsApp, sem URL ou número. Nenhum contato foi inventado.
- **155 — Transurc Campinas:** menciona um 0800 sem informar o número completo. A coluna de taxa usa a grafia `De R$ 11,8 a R$ 47,20`; o procedimento preserva os valores por via.

A data de vigência não está estabelecida no material. A ingestão usa `validation_only` e escopo `local_review`, disponíveis apenas no desenvolvimento. Validar vigência de taxas, contatos e procedimentos com a área responsável antes de disponibilização institucional. Não houve deploy em produção nem atualização destrutiva do corpus anterior.

## Operação local e testes

```powershell
$pdfPath = 'C:/Users/douglas.amaral/Downloads/orientações segunda via cartões vt (1).pdf'
docker compose run --rm -v "${pdfPath}:/input/vt.pdf:ro" api python -m app.rag.transport_ingest /input/vt.pdf --approve --local-review --scope local_review
# Repetir o mesmo comando não duplica chunks.
docker compose exec -e RUN_DB_TESTS=1 -e RUN_OPERATIONAL_LIVE=1 -e RUN_RAG02_LIVE=1 api pytest -q
docker compose run --rm -e RUN_TRANSPORT_LIVE=1 -v "${pdfPath}:/input/vt.pdf:ro" api pytest tests/test_transport.py tests/test_transport_live.py -q
npm test
npm run build
npm run lint
npm run format:check
npm run test:transport:browser
```

O teste de navegador requer Vite e API locais ativos. Os testes reais de VT verificaram SPTrans, TOP, SOU Diadema, Guarulhos e Eroles (empresa), além de acompanhamento sobre taxa/prazo, nome/código inexistente, troca de cartão e fontes. A verificação percorreu os 33 códigos com embeddings reais, comparando procedimento e taxa do resultado com a linha extraída, sem mistura entre operadoras. Também verificou reindexação sem duplicação e filtro de escopo vazio. Testes de extração usam o PDF montado somente para leitura, não uma cópia incorporada à imagem.

Resultados de backend: 65 aprovados na execução com testes reais de VT e integração; 87 aprovados na execução da regressão completa de Folha Ponto e orientações operacionais. As execuções cobrem 89 testes distintos; dois testes legados opcionais da base fictícia permanecem fora dessas execuções. Frontend: 19 testes aprovados, build, lint e formatação. Edge real: PASS em 1440×900, 1366×768, 390×844 e 390×400, com seleção dos 33 cartões, busca, teclado, recarregamento, fonte exata, link de e-mail, acompanhamento, troca de cartão, nome desconhecido, responsabilidade da empresa e mudança para holerite. Sem erros de console, rolagem global ou compositor fora da tela. Capturas em `tmp/transport-qa/`. O hook mantém o envio ocupado até sincronizar mensagens e estado da conversa, evitando ações sobre uma seleção desatualizada.

## Arquivos principais

Criados: `backend/app/rag/transport_extract.py`, `transport_ingest.py`, `backend/app/support/transport.py`, `backend/migrations/versions/0004_transport_cards.py`, `backend/tests/test_transport.py`, `test_transport_live.py`, `src/components/TransportCards.tsx`, `TransportCards.test.tsx`, `scripts/transport-browser-check.cjs` e este relatório.

Modificados: modelos e consulta RAG, configuração de versão/perfil, schemas, rotas, preparação de mensagens, LangGraph, classificador Ollama, catálogo de atendimento, estado/ações frontend e hook de sincronização, Chat, CSS, scripts npm e README. Não foram adicionados frameworks, microsserviços ou dependências.
