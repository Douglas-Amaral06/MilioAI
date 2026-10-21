# Sprint de UX — experiência conversacional

## Comportamentos entregues

- Respostas do assistente têm uma ação de cópia por mensagem. No desktop ela aparece por hover ou foco; no toque permanece visível. A Clipboard API recebe apenas texto, com parágrafos, quebras, marcadores de listas e destinos dos links que fazem parte da resposta. Marcadores internos `[fonte:...]`, horários, nomes de autores, anexos e fontes documentais separadas não são copiados. O texto original permanece intacto.
- O ícone muda para confirmação e o status acessível anuncia **Copiado** por 2,5 segundos. Permissão negada ou API indisponível apresentam **Não foi possível copiar**, sem alert nativo ou fallback que altere a seleção. Respostas em processamento ainda não oferecem cópia de conteúdo parcial.
- **Ir para a última mensagem** aparece a mais de 160 px do final do histórico, dentro da área de conversa e acima do composer. O retorno é suave, ou imediato com `prefers-reduced-motion`. O foco retorna à região do histórico sem rolar o documento.
- A conversa acompanha o streaming enquanto estiver a até 64 px do final. A leitura de mensagens antigas é preservada. Uma nova mensagem do usuário e a troca de conversa levam ao final; a atualização de uma resposta não força a posição de leitura.
- O composer indica **Enviando mensagem…** antes da confirmação e **Resposta em andamento.** após o evento `start`. O rascunho só é limpo na confirmação, inclusive quando o envio cria a primeira conversa. Estados de carregamento e erro não acrescentam linhas ao composer.
- O bloqueio síncrono existente no hook e as verificações do formulário impedem envios duplicados. Falhas não removem o histórico; erros de transporte e eventos de erro apresentam mensagens locais compreensíveis, sem expor detalhes internos da API. Não há retry automático nem botão de repetição de mensagem.
- Pesquisas e listas vazias de instrutores/cartões têm textos específicos. O retry já existente para carregar essas listas permanece restrito a leituras GET.

## Arquivos desta sprint

Novos:

- `src/components/CopyResponse.tsx`: cópia, confirmação, erros, temporizador e limpeza.
- `src/components/messageText.ts` e `messageText.test.ts`: texto visível, conversão para clipboard e testes.
- `src/hooks/useConversationScroll.ts`: posição interna, acompanhamento, redimensionamento e retorno ao final.
- `scripts/ux-browser-check.cjs`: testes de interação no navegador.
- `docs/UX-SPRINT.md`: este relatório.

Atualizados:

- `src/components/Chat.tsx` e `Chat.module.css`: ações, posicionamento, estados e estilos com os tokens existentes.
- `src/components/Icon.tsx`: ícones de cópia, confirmação, seta para baixo e processamento.
- `src/components/Composer.tsx`, `src/hooks/useWorkspace.ts` e `src/App.tsx`: fases visuais de envio, preservação do rascunho e mensagens de erro.
- `src/components/InstructorFlow.tsx`, `TransportCards.tsx` e `Sidebar.tsx`: estados vazios e feedback acessível.
- `scripts/offline-browser-check.cjs`: asserções atualizadas para os novos textos de processamento e interrupção.
- `package.json`: comando `test:ux:browser`.
- `README.md`: acesso a este relatório e instrução de teste.

## Decisões e isolamento

Não foram acrescentadas dependências. As funcionalidades usam o mesmo Chat em produção e no modo offline; não há verificações de origem dos dados nos novos controles. O adaptador offline e os contratos da API permanecem inalterados.

A rolagem usa uma ref da região interna e `ResizeObserver`, com trabalho agrupado por `requestAnimationFrame`. Listeners, observer, frames e temporizadores têm limpeza na desmontagem. Nenhuma chamada de rolagem global ou `scrollIntoView` foi adicionada à aplicação.

As ações têm nomes acessíveis e alvos de 44 px. O layout reserva espaço para feedback de cópia e envio. As transições são curtas e obedecem à regra de movimento reduzido existente. O streaming não é colocado em uma região live de texto integral; os anúncios de status mudam somente nas transições de fase.

## Verificação

Resultado desta sprint: typecheck, ESLint, 36 testes unitários, build de produção, suíte de UX e regressão offline aprovados. Os testes offline registraram zero chamadas externas/à API e zero erros de página. O build final manteve a API real e não incluiu os dados ou controles offline.

Na pasta que contém o `package.json`:

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npm run test:ux:browser
npm run test:offline:browser
```

Os testes unitários cobrem também a conversão de respostas curtas/longas, listas, links e remoção de citações internas. A suíte de UX usa Edge headless e a Clipboard API real do Windows, além de simular permissão negada/API ausente. Exercita retorno suave, movimento reduzido, streaming, posição de leitura, troca de conversa, histórico recarregado, ausência de scroll global, toque e cinco tamanhos: 1440×900, 1366×768, 768×1024, 390×844 e 390×400. Capturas ficam em `tmp/ux-qa/`.

Para falhas antes e depois da confirmação, a suíte usa o cliente real em modo normal com respostas HTTP/SSE controladas no próprio teste. Verifica rascunho, estabilidade do composer, bloqueio de submissões repetidas, sanitização dos erros, uso após falha, links e listas vazias. A suíte offline cobre assuntos, perguntas guiadas, instrutores, cartões, fontes, persistência e cancelamento, rejeitando requisições externas ou à API.

Os testes de navegador iniciam e encerram seus próprios servidores Vite. Deixe livres as portas 5173 e 5174. Edge deve estar instalado; outro canal compatível pode ser escolhido com `PLAYWRIGHT_CHANNEL`.

## Limitações

Copiar exige a Clipboard API em contexto seguro (HTTPS ou localhost), além das permissões do navegador. Quando indisponível, o erro é informado. Não há fallback legado. O fluxo de envio foi testado com contratos HTTP/SSE reais e respostas controladas, sem iniciar serviços de backend; isso não substitui uma homologação integrada no ambiente corporativo. Não foi realizada uma auditoria com leitor de tela real.

Nenhum arquivo de backend foi alterado nesta sprint. Os hashes dos 64 arquivos de backend existentes foram comparados ao estado inicial, incluindo as alterações que já estavam no workspace antes desta tarefa.
