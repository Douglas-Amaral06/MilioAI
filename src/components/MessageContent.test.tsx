import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MessageContent } from "./MessageContent";
import { safeLink } from "./safeLink";

describe("message formatting", () => {
  it("renders paragraphs, lists, emphasis and safe links", () => {
    const html = renderToStaticMarkup(
      <MessageContent
        content={
          "Olá **aprendiz**.\n\n- Primeiro\n- Segundo\n\n1. Assine\n2. Envie\n\n[Portal](https://conectajovem.dema.org.br)"
        }
      />,
    );
    expect(html).toContain("<strong>aprendiz</strong>");
    expect(html).toContain("<ul><li>Primeiro</li><li>Segundo</li></ul>");
    expect(html).toContain('<ol start="1">');
    expect(html).toContain('rel="noopener noreferrer"');
  });
  it("escapes HTML and rejects executable links", () => {
    const html = renderToStaticMarkup(
      <MessageContent
        content={"<img src=x onerror=alert(1)> [Abrir](javascript:alert)"}
      />,
    );
    expect(html).toContain("&lt;img");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("href=");
    for (const value of [
      "javascript:alert(1)",
      "data:text/html,test",
      "//example.com",
      "https://example.com\n",
    ])
      expect(safeLink(value)).toBe(false);
  });
  it("keeps line breaks and incomplete streaming text", () => {
    expect(
      renderToStaticMarkup(
        <MessageContent content={"Linha um\nLinha dois **parcial"} />,
      ),
    ).toContain("Linha um\nLinha dois **parcial");
  });
});
