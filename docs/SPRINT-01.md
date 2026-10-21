# Relatório · Sprint 01

Entrega em 15 de outubro de 2026. Frontend implementado em workspace inicialmente vazio; não houve arquivos preexistentes substituídos nem serviços externos iniciados.

## Implementação

Aplicação React + TypeScript strict + Vite com conversas locais, busca por título, seleção, renomeação, exclusão confirmada, rascunhos independentes e envio de mensagens do usuário. Sugestões apenas preenchem o composer. O aviso sobre indisponibilidade das respostas é informativo, separado das mensagens. Painel de fontes vazio, sem documentos ou referências inventados.

`src/components` concentra Sidebar, Chat, Composer, SourcesPanel, Modal e Icon; `src/hooks` gerencia o estado e a persistência; `src/data` separa transições puras e adaptador de armazenamento; `src/styles` contém tokens e base visual; `src/types.ts` define os contratos. A árvore completa e os comandos de execução estão no README. Não foi necessário Context API ou React Router.

## Design e manual

Referência: manual Demà fornecido em PDF, páginas 15–20 (logotipo) e 23–32 (cor, tipografia e grafismos). Extração textual dessas páginas e renderização das páginas 23–32; inspeção visual das páginas 27 e 31 para acessibilidade e sobreposições. O renderizador alertou sobre uma fonte incorporada inválida no próprio PDF; o texto foi extraído e as páginas renderizadas permitiram a conferência. Nenhuma fonte ou marca oficial foi extraída.

Paleta oficial centralizada em tokens, superfícies brancas, carbono no texto, amarelo e vermelho em detalhes e azul nas ações. Os neutros servem a legibilidade e divisórias. Composição editorial com alinhamento do conteúdo e composer, sugestões numeradas em linhas e um único conjunto de grafismos no estado inicial. A diagonal usa 20°. A proporção cromática foi adaptada à leitura da interface, conforme autorizado no briefing.

Space Grotesk é empacotada localmente pelo Fontsource com licença SIL OFL. A assinatura MilioAI e seu favicon tipográfico são provisórios. Comunicação/Marketing precisa validar uso da fonte, identidade do produto, grafismos e distribuição cromática antes da aplicação institucional. O logotipo Demà não foi aplicado ou recriado.

## Validação realizada

| Verificação                       | Resultado                         |
| --------------------------------- | --------------------------------- |
| Instalação npm e lockfile         | Concluída                         |
| TypeScript strict                 | Sem erros                         |
| ESLint                            | Sem erros ou avisos               |
| Vitest                            | 7 testes aprovados                |
| Build de produção Vite            | Concluído                         |
| Chrome / Playwright               | Fluxo completo aprovado           |
| Larguras 1440, 1280, 768 e 390 px | Sem overflow horizontal detectado |
| Console no fluxo de navegador     | Nenhum erro ou aviso              |

Os testes unitários cobrem envio sem resposta artificial, persistência de mensagens/rascunhos, alternância de rascunhos, envio vazio, título renomeado, exclusão ativa, contrato inválido, acesso/quota indisponíveis e IDs duplicados. São 7 casos agrupando essas verificações.

O script `scripts/browser-check.cjs` verifica sugestões sem envio, envio por Enter, quebra por Shift + Enter, restauração após reload, seleção e rascunhos independentes, renomeação, busca sem distinguir acentos, busca sem resultados, cancelamento e confirmação de exclusão, recolhimento da navegação, criação no celular, contenção de Tab no diálogo, Escape, retorno de foco, fontes vazias e ausência de mensagens artificiais. Ele também verifica overflow nas quatro larguras e captura console e erros da página.

Houve revisão visual das capturas do estado inicial em desktop, notebook, tablet e celular, da conversa com fontes em desktop e dos estados de conversa e fontes no celular. A segunda revisão corrigiu o nome acessível do botão de fontes no mobile, fortaleceu o ciclo de foco nos diálogos, removeu títulos/controles duplicados dos painéis mobile e aumentou textos auxiliares e o campo de mensagem no celular.

As primeiras execuções de Vite/Vitest/build foram bloqueadas pelo sandbox do ambiente (acesso negado do esbuild), e passaram após execução autorizada fora dessa restrição. As ferramentas de lint foram atualizadas para versões suportadas após o aviso de descontinuação da versão inicialmente resolvida. Isso não exige alterações no código para execução local comum.

Capturas de evidência ficam em `docs/qa/`. Não representam conteúdo inicial pré-carregado: foram geradas em contexto isolado com mensagens fictícias de teste.

## Limites e próximos passos

- Persistência temporária no localStorage, sem sincronização entre abas/dispositivos, garantia de retenção ou recuperação de exclusões. Não inserir dados pessoais/sensíveis. Falhas de armazenamento mantêm a sessão em memória e exibem aviso.
- A verificação responsiva utilizou viewports no Chrome em Windows. Não foram realizados testes físicos em iOS/Android, teclado virtual, Safari/Firefox ou auditoria com leitor de tela. Os comportamentos essenciais de teclado foram verificados; não se declara certificação de acessibilidade.
- Nenhuma IA, autenticação, base de conhecimento, RAG, agente, API, backend, banco ou serviço de infraestrutura foi instalado/configurado.
- A integração futura com FastAPI precisa de contrato real, autenticação/autorização, operações assíncronas, estados de erro/cancelamento, retenção e política de privacidade. O adaptador `WorkspaceRepository` e os contratos de conversas/mensagens/referências são os pontos de evolução; não há cliente HTTP fictício.
- A aplicação institucional de Space Grotesk, assinatura MilioAI, favicon e grafismos depende de validação com Comunicação/Marketing. A POC não pressupõe aprovação da identidade do produto.
