import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TransportCards } from "./TransportCards";
const noop = () => {};
describe("Transport card selection", () => {
  it("offers labelled search without procedures", () => {
    const html = renderToStaticMarkup(
      <TransportCards
        state={{ vt_stage: "selection" }}
        busy={false}
        onAction={noop}
      />,
    );
    expect(html).toContain("Buscar cartão ou operadora");
    expect(html).toContain('type="search"');
    expect(html).not.toContain("Quem paga");
    expect(html).not.toContain("7 tarifas");
  });
  it("lets the user change the persisted card", () => {
    const html = renderToStaticMarkup(
      <TransportCards
        state={{ vt_stage: "active", selected_card_code: "89" }}
        busy
        onAction={noop}
      />,
    );
    expect(html).toContain("Trocar cartão de transporte");
    expect(html).toContain("disabled");
  });
  it("does not open another subject panel", () => {
    expect(
      renderToStaticMarkup(
        <TransportCards
          state={{ vt_stage: "idle", selected_card_code: "89" }}
          busy={false}
          onAction={noop}
        />,
      ),
    ).toBe("");
  });
});
