import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { InstructorFlow } from "./InstructorFlow";
import { MessageContent } from "./MessageContent";
const noop = () => {};
describe("Instructor flow", () => {
  it("keeps confirmation accessible and disabled while busy", () => {
    const html = renderToStaticMarkup(
      <InstructorFlow
        state={{ asked: true, stage: "confirmation" }}
        busy
        onAction={noop}
      />,
    );
    expect(html).toContain("Sim, sei quem é.");
    expect(html).toContain("Não sei quem é.");
    expect(html).toContain("disabled");
    expect(html).not.toContain("@renapsi");
  });
  it("has a labelled search and cancellation, without embedding contacts", () => {
    const html = renderToStaticMarkup(
      <InstructorFlow
        state={{ asked: true, stage: "selection" }}
        busy={false}
        onAction={noop}
      />,
    );
    expect(html).toContain("Buscar instrutor pelo nome");
    expect(html).toContain('type="search"');
    expect(html).toContain("Cancelar seleção");
    expect(html).not.toContain("@renapsi");
  });
  it("allows resuming and renders trusted contact links safely", () => {
    expect(
      renderToStaticMarkup(
        <InstructorFlow
          state={{ asked: true, stage: "contact" }}
          busy={false}
          onAction={noop}
        />,
      ),
    ).toContain("Voltar à lista");
    const html = renderToStaticMarkup(
      <MessageContent content="[Conecta Jovem](https://conectajovem.dema.org.br/) [Educacional](mailto:educacional.sp@renapsi.org.br) [Telefone](tel:+5511998030631)" />,
    );
    expect(html).not.toContain('href="tel:');
    expect(html).toContain('href="mailto:educacional.sp@renapsi.org.br"');
    expect(html).toContain('rel="noopener noreferrer"');
  });
});
