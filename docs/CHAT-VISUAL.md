# Refinamento visual do chat

Mensagens do usuário usam balão azul claro, largura conforme o conteúdo e alinhamento à direita. O remetente permanece identificado para leitores de tela. Respostas do MilioAI ficam à esquerda, sobre fundo branco, com assinatura discreta. As divisórias entre mensagens foram removidas.

Arquivos: `Chat.tsx`, `Chat.module.css`, `MessageContent.tsx`, `safeLink.ts` e `MessageContent.test.tsx` em `src/components`.

O renderizador suporta parágrafos, quebras de linha, listas numeradas e simples, negrito e links Markdown. HTML é tratado como texto; links aceitam somente HTTP, HTTPS e mailto. Não foram adicionadas dependências. Fontes continuam expansíveis junto à resposta. Backend, autenticação, navegação e contratos da API foram preservados.

Validação: 13 testes unitários, build e ESLint; integração no Edge com SSE real, fontes, persistência após recarregar, perguntas guiadas, múltiplos turnos, troca de assunto e anexos. Layout conferido em 1440×900, 1366×768, 390×844, 320×568 e 390×400. Fixture isolada verificou conteúdo longo, palavras extensas, links, listas e estados de processamento/erro. Sem rolagem global ou transbordamento horizontal; compositor visível. Teclado físico de celular não foi testado.
