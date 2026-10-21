import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SupportMenu } from "./SupportMenu";
import type { SupportTopic } from "../api/client";
const topics: SupportTopic[] = [
  {
    topic_id: "folha_ponto",
    title: "Folha Ponto",
    domain: "rh_frequency",
    agent_id: "rh_frequency",
    enabled: true,
    ordering: 0,
    questions: [
      {
        question_id: "folha_ponto.prazo",
        topic_id: "folha_ponto",
        text: "Qual é o prazo?",
        enabled: true,
        ordering: 0,
      },
    ],
  },
  {
    topic_id: "outros",
    title: "Outros",
    domain: "auto",
    agent_id: null,
    enabled: true,
    ordering: 1,
    questions: [],
  },
];
const noop = () => {};
describe("Atendimento guiado", () => {
  it("renderiza apenas o catálogo recebido", () => {
    const html = renderToStaticMarkup(
      <SupportMenu
        topics={topics}
        hasMessages={false}
        busy={false}
        onTopic={noop}
        onQuestion={noop}
      />,
    );
    expect(html).toContain("Folha Ponto");
    expect(html).toContain("Outros");
    expect(html).not.toContain("Qual é o prazo?");
  });
  it("mostra perguntas e navegação do assunto", () => {
    const html = renderToStaticMarkup(
      <SupportMenu
        topics={topics}
        topicId="folha_ponto"
        hasMessages={false}
        busy={true}
        onTopic={noop}
        onQuestion={noop}
      />,
    );
    expect(html).toContain("Qual é o prazo?");
    expect(html).toContain("Voltar aos assuntos");
    expect(html).toContain("disabled");
  });
  it("Outros convida a escrever sem impor perguntas", () => {
    const html = renderToStaticMarkup(
      <SupportMenu
        topics={topics}
        topicId="outros"
        hasMessages={false}
        busy={false}
        onTopic={noop}
        onQuestion={noop}
      />,
    );
    expect(html).toContain("Escreva sua dúvida");
    expect(html).not.toContain("Qual é o prazo?");
  });
});
