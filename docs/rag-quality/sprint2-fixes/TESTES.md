# Verificações executadas

- Backend, versão final: `RUN_DB_TESTS=1 python -m pytest -q -m 'not live'`: **135 passaram**, 29 testes live não selecionados. Inclui testes novos de intenção, desambiguação, continuidade no grafo, código inexistente, proveniência, seleção de instrutor e contexto explícito; inclui regressão de isolamento, autenticação, persistência, grounding e múltiplas intenções.
- Serviços reais: `RUN_OPERATIONAL_LIVE=1 RUN_PERSPECTIVE_LIVE=1 python -m pytest -q tests/test_operational_live.py tests/test_perspective_live.py`: **17 passaram**. Exercita Ollama, PostgreSQL e serviços FastAPI com autenticação existente, inclusive sequência de seleção de instrutor e troca de assunto.
- Regressão real Sprint 1: **8 cenários verificados**: 3 saudações/agradecimento, 3 solicitações individuais e 2 composições Folha Ponto + VT. Streaming corresponde ao resultado final; os casos compostos recuperam fontes dos dois domínios. Evidências em `sprint1-regression.json`.
- Pacote de qualidade: `python -m unittest discover -s docs/rag-quality/tests -q`: **39 passaram**. O avaliador e seus critérios não foram alterados.
- Ruff: `python -m ruff check --no-cache app tests/test_sprint2_fixes.py`: sem erros na versão testada.
- A primeira regressão real registrou **1 falha e 16 sucessos**: flexão “gero” classificada como documental. A falha e o log foram preservados; depois da correção, os 17 passaram.
- Testes live que fazem ingestão/reindexação não foram executados. Os testes de integração usam registros próprios de teste; nenhum documento institucional foi removido ou reindexado.

As cópias de código foram executadas em `/tmp/sprint2-fixes/backend` no contêiner existente. A aplicação usada pela avaliação é criada a partir dessas cópias e usa os serviços reais existentes. O processo da API que já estava no ar não foi substituído nem reiniciado. As mudanças estão no workspace; a aplicação em uso precisa ser reiniciada com essa versão quando for incorporada.

Os arquivos XML anexos registram os resultados finais dos testes de backend e dos testes live. Os exports e checkpoints registram as avaliações reais; resultados lexicais não autorizam aprovação semântica.
