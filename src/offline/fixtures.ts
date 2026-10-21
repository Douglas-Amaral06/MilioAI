import type { SupportTopic } from "../api/remote";
const catalog: [string, string, [string, string][]][] = [
  [
    "folha_ponto",
    "Folha Ponto",
    [
      ["prazo", "Qual é o prazo de entrega da folha ponto?"],
      ["preenchimento", "Como preencher minha folha ponto corretamente?"],
    ],
  ],
  [
    "atestados",
    "Atestados",
    [
      ["envio", "Onde devo enviar meu atestado?"],
      ["curso", "Onde envio meu atestado referente ao curso?"],
    ],
  ],
  [
    "vale_transporte",
    "Benefício Vale-Transporte",
    [
      ["credito", "Onde é pago ou creditado meu vale-transporte?"],
      [
        "segunda_via",
        "Como solicito a segunda via do meu cartão de vale-transporte?",
      ],
    ],
  ],
  [
    "vale_refeicao_alimentacao",
    "Benefício Vale-Refeição / Alimentação",
    [
      [
        "funcionamento",
        "Como funciona o benefício de refeição ou alimentação?",
      ],
    ],
  ],
  [
    "salario",
    "Salário",
    [
      ["data", "Quando recebo meu salário?"],
      ["holerite", "Onde consulto meu holerite?"],
    ],
  ],
  [
    "falta_curso",
    "Falta no Curso",
    [
      ["instrutor", "Como descubro quem é meu instrutor?"],
      ["justificar", "Como justificar uma ausência no dia de capacitação?"],
    ],
  ],
  [
    "falta_trabalho",
    "Falta no Trabalho",
    [["registro", "Como registro uma falta na folha ponto?"]],
  ],
  ["outros", "Outros", [["calendario", "Onde consulto meus dias de curso?"]]],
];
export const topics: SupportTopic[] = catalog.map(
  ([topic_id, title, questions], ordering) => ({
    topic_id,
    title,
    ordering,
    domain: "demo",
    agent_id: null,
    enabled: true,
    questions: questions.map(([id, text], index) => ({
      question_id: `${topic_id}.${id}`,
      topic_id,
      text,
      ordering: index,
      enabled: true,
    })),
  }),
);
export const instructors = [
  { id: "demo-ana", name: "Ana Exemplo", contact: "ana@example.invalid" },
  { id: "demo-bruno", name: "Bruno Demonstração", contact: null },
  {
    id: "demo-cecilia",
    name: "Cecília Exemplo",
    contact: "cecilia@example.invalid",
  },
];
export const cards = [
  { code: "demo-sp", name: "Cartão Aurora · Operadora Exemplo", uf: "SP" },
  { code: "demo-rj", name: "Cartão Horizonte · Operadora Modelo", uf: "RJ" },
  { code: "demo-mg", name: "Cartão Caminho · Operadora Local", uf: "MG" },
];
export const sources = [
  {
    id: "demo-source",
    title: "Guia demonstrativo local",
    version: "demo-1",
    is_test: true,
    validation_only: true,
    excerpt:
      "Conteúdo fictício para testar a interface. Sem validade institucional.",
  },
];
export const scenarios = {
  success:
    "Esta é uma resposta demonstrativa curta. Nenhum serviço de IA foi consultado.",
  sources:
    "Exemplo com fonte local.\n\n- Consulte os detalhes da fonte abaixo.\n- Este conteúdo não define procedimentos institucionais.\n\n[Abrir demonstração local](http://127.0.0.1:5173/#message)",
  long: Array.from(
    { length: 8 },
    (_, i) =>
      `**Exemplo ${i + 1}**\n\nEsta seção ilustra uma resposta longa para validar a rolagem e a leitura.\n\n- Informação fictícia.\n- Sem taxas, prazos ou orientações vigentes.`,
  ).join("\n\n"),
  empty:
    "Não há informações disponíveis neste cenário demonstrativo. Nenhuma busca real foi realizada.",
  error: "Falha controlada da demonstração local.",
  slow: "Resposta demonstrativa com processamento lento para testar o cancelamento.",
};
export type Scenario = keyof typeof scenarios;
