# Relatório de avaliação offline

Inspeção técnica: 2026-10-20. Dataset: 1.0.0. Validação estrutural: aprovada. Testes do avaliador: 37 aprovados. Nenhuma execução de RAG ou modelo foi realizada; desempenho de recuperação, geração e precisão não foi medido. Não foram reutilizados scores históricos como resultados desta avaliação.

| Inventário validado        | Quantidade |
| -------------------------- | ---------: |
| Casos                      |         76 |
| Folha ponto                |         20 |
| VT                         |         47 |
| Operacional                |          5 |
| Governança                 |          4 |
| Cartões distintos cobertos |   33 de 33 |
| Evidências                 |         50 |
| Registros documentais      |          5 |
| Fontes aprovadas           |          0 |
| Pendências registradas     |          9 |

A cobertura de cartões refere-se aos snapshots disponíveis: 24 linhas na página 1 e 9 na página 2. Não comprova completude ou atualidade de um PDF original não fornecido. Os mínimos de casos de folha ponto, cartões distintos, continuidade e ausência/ambiguidade foram atendidos.

Pendências incluem originais ausentes; múltiplas tarifas e procedimento divergente no código 3854; responsável pela solicitação divergente no 503; endereço ausente no 15779; canal sem número/link no 9156; telefone incompleto e taxas por via no 155; canal de folha ponto sem prova de substituição pela configuração operacional; contato de instrutor ausente; configuração habilitada sem aprovação institucional. Consulte `conflicts.md` para localização, impacto e ação necessária. Nenhum conflito foi resolvido por suposição.

A conferência usa imagens locais e extrações derivadas, além da configuração operacional existente. Não foram cadastrados contatos pessoais no dataset. Vigência, responsáveis e aprovação permanecem desconhecidos. A evidência permite uma base provisória para revisão, não uma certificação de resposta de produção.

As métricas reais permanecem não medidas. `results_template.json` tem resultados vazios, `run_kind=template` e data de execução nula; o avaliador recusa esse arquivo como execução real. Os testes usam entradas sintéticas explicitamente identificadas apenas para verificar cálculos, referências e rejeições. Nenhum score desses testes é desempenho do MilioAI.

Para reproduzir a validação e os testes, siga `README.md`. Para avaliar uma execução futura já realizada e exportada, siga `EXPORT.md`. O pacote não depende de FastAPI, Docker, PostgreSQL, Supabase, Ollama ou rede e não altera agentes, API, banco ou recuperação da aplicação.
