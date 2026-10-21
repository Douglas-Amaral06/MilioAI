import { describe, expect, it } from "vitest";
import { clipboardMessageText, visibleMessageText } from "./messageText";

describe("texto copiado da resposta", () => {
  it("preserva parágrafos, quebras e marcadores de listas sem copiar HTML", () => {
    expect(
      clipboardMessageText(
        "Olá **aprendiz**.\r\n\r\n- Um\r\n- Dois\r\n\r\n1. Etapa\r\n2. Próxima\r\nFim",
      ),
    ).toBe("Olá aprendiz.\n\n- Um\n- Dois\n\n1. Etapa\n2. Próxima\nFim");
  });
  it("copia links presentes na resposta, sem referências técnicas", () => {
    expect(
      clipboardMessageText(
        "[Portal](https://example.com)\n[Email](mailto:demo@example.invalid) [fonte:documento-privado]",
      ),
    ).toBe(
      "Portal (https://example.com)\nEmail (mailto:demo@example.invalid) ",
    );
    expect(visibleMessageText("Texto [fonte:incompleta")).toBe("Texto ");
  });
  it("não restaura destinos bloqueados pelo renderizador", () => {
    expect(
      clipboardMessageText("[Abrir](javascript:blocked) e **texto**"),
    ).toBe("Abrir e texto");
  });
  it("não altera a mensagem original, incluindo respostas longas", () => {
    const message =
      "**Exemplo**\n\n- Informação\n\n".repeat(100) + "[fonte:interno]";
    const before = message;
    expect(clipboardMessageText(message)).toBe(
      "Exemplo\n\n- Informação\n\n".repeat(100),
    );
    expect(message).toBe(before);
  });
});
