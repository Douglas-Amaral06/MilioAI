import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import {
  request,
  streamMessage,
  resetDemo,
  setScenario,
  storageKey,
} from "./adapter";
import type {
  RemoteConversation,
  RemoteMessage,
  StreamEvent,
  SupportTopic,
} from "../api/remote";
const values = new Map<string, string>();
const network = vi.fn(() => {
  throw new Error("Acesso à rede proibido");
});
const sessionRead = vi.fn(() => {
  throw new Error("Sessão real não deve ser acessada");
});
beforeEach(() => {
  values.clear();
  setScenario("success");
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => values.get(k) ?? null,
    setItem: (k: string, v: string) => values.set(k, v),
    removeItem: (k: string) => values.delete(k),
  });
  vi.stubGlobal("sessionStorage", { getItem: sessionRead });
  vi.stubGlobal("fetch", network);
  network.mockClear();
  sessionRead.mockClear();
});
afterEach(() => {
  expect(network).not.toHaveBeenCalled();
  expect(sessionRead).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});
async function create() {
  return request<RemoteConversation>("/conversations", {
    method: "POST",
    body: JSON.stringify({ title: "Teste local" }),
  });
}
async function send(
  id: string,
  payload: object = { content: "Olá" },
  controller = new AbortController(),
) {
  const events: StreamEvent[] = [];
  await streamMessage(id, payload, controller.signal, (event) =>
    events.push(event),
  );
  return events;
}
describe("adaptador offline", () => {
  it("carrega oito assuntos e identidade fictícia", async () => {
    expect(await request("/me")).toMatchObject({ id: "demo-local" });
    expect(await request<SupportTopic[]>("/support/topics")).toHaveLength(8);
  });
  it("cria, renomeia, pagina, persiste após recarga e exclui conversas", async () => {
    const row = await create();
    await request(`/conversations/${row.id}`, {
      method: "PATCH",
      body: '{"title":"Renomeada"}',
    });
    vi.resetModules();
    const reloaded = await import("./adapter");
    expect(await reloaded.request(`/conversations/${row.id}`)).toMatchObject({
      title: "Renomeada",
    });
    expect(await request("/conversations?limit=1&offset=1")).toEqual([]);
    await request(`/conversations/${row.id}`, { method: "DELETE" });
    expect(await request("/conversations")).toEqual([]);
  });
  it("envia pergunta guiada, continua conversa e preserva mensagens", async () => {
    const row = await create();
    await request(`/conversations/${row.id}/topic`, {
      method: "PATCH",
      body: '{"topic_id":"folha_ponto"}',
    });
    const events = await send(row.id, {
      topic_id: "folha_ponto",
      question_id: "folha_ponto.prazo",
    });
    expect(events[0]).toMatchObject({
      event: "start",
      user: { content: "Qual é o prazo de entrega da folha ponto?" },
    });
    expect(events.at(-1)).toMatchObject({
      event: "done",
      message: { status: "complete" },
    });
    await send(row.id);
    expect(
      await request<RemoteMessage[]>(`/conversations/${row.id}/messages`),
    ).toHaveLength(4);
    await request(`/conversations/${row.id}/topic`, {
      method: "PATCH",
      body: '{"topic_id":null}',
    });
    expect(await request(`/conversations/${row.id}`)).toMatchObject({
      topic_id: null,
      support_state: {},
    });
  });
  it("seleciona instrutor com contato e sem contato, cancela e retoma", async () => {
    const row = await create();
    await send(row.id, {
      topic_id: "falta_curso",
      question_id: "falta_curso.instrutor",
    });
    expect(await request(`/conversations/${row.id}`)).toMatchObject({
      support_state: { stage: "confirmation" },
    });
    for (const kind of [
      "instructor_known",
      "instructor_unknown",
      "instructor_resume",
    ]) {
      await send(row.id, { action: { kind } });
      expect(await request(`/conversations/${row.id}`)).toMatchObject({
        support_state: { stage: "selection" },
      });
    }
    expect(await request("/support/instructors")).toHaveLength(3);
    for (const instructor_id of ["demo-ana", "demo-bruno"]) {
      const events = await send(row.id, {
        action: { kind: "instructor_select", instructor_id },
      });
      expect(events.at(-1)).toMatchObject({
        event: "done",
        message: {
          content: expect.stringContaining(
            instructor_id === "demo-ana"
              ? "ana@example.invalid"
              : "contato não informado",
          ),
        },
      });
    }
    await send(row.id, { action: { kind: "instructor_cancel" } });
    expect(await request(`/conversations/${row.id}`)).toMatchObject({
      support_state: { stage: "idle" },
    });
  });
  it("seleciona e troca cartões demonstrativos", async () => {
    const row = await create();
    expect(await request("/support/transport-cards")).toHaveLength(3);
    await send(row.id, {
      topic_id: "vale_transporte",
      question_id: "vale_transporte.segunda_via",
    });
    for (const benefit_code of ["demo-sp", "demo-rj"]) {
      await send(row.id, { action: { kind: "card_select", benefit_code } });
      expect(await request(`/conversations/${row.id}`)).toMatchObject({
        support_state: { vt_stage: "active", selected_card_code: benefit_code },
      });
      await send(row.id, { action: { kind: "card_change" } });
      expect(await request(`/conversations/${row.id}`)).toMatchObject({
        support_state: { vt_stage: "selection" },
      });
    }
  });
  it("fornece fontes, resposta longa e ausência de informação", async () => {
    const row = await create();
    setScenario("sources");
    expect(await send(row.id)).toContainEqual({
      event: "sources",
      sources: [expect.objectContaining({ is_test: true })],
    });
    setScenario("long");
    expect(
      (await send(row.id)).filter((e) => e.event === "delta").length,
    ).toBeGreaterThan(10);
    setScenario("empty");
    expect((await send(row.id)).at(-1)).toMatchObject({
      event: "done",
      message: { content: expect.stringContaining("Não há informações") },
    });
  });
  it("persiste falha controlada e cancelamento sem deixar processamento pendente", async () => {
    const row = await create();
    setScenario("error");
    expect((await send(row.id)).at(-1)).toMatchObject({
      event: "error",
      code: "demo_failure",
    });
    setScenario("slow");
    const controller = new AbortController();
    await streamMessage(
      row.id,
      { content: "Cancelar" },
      controller.signal,
      (event) => {
        if (event.event === "start") controller.abort();
      },
    );
    const messages = await request<RemoteMessage[]>(
      `/conversations/${row.id}/messages`,
    );
    expect(messages.at(-1)?.status).toBe("cancelled");
    expect(messages.some((m) => m.status === "processing")).toBe(false);
  });
  it("isola e limpa somente dados demo; recusa uploads e caminhos desconhecidos", async () => {
    values.set("milioai.workspace.v1", "real");
    values.set("milioai.auth.session.v1", "token-real");
    const row = await create();
    await expect(
      request(`/conversations/${row.id}/attachments`, {
        method: "POST",
        body: new FormData(),
      }),
    ).rejects.toThrow("Nenhum arquivo");
    await expect(request("/unknown")).rejects.toThrow("indisponível");
    expect(values.has(storageKey)).toBe(true);
    resetDemo();
    expect([...values.entries()]).toEqual([
      ["milioai.workspace.v1", "real"],
      ["milioai.auth.session.v1", "token-real"],
    ]);
  });
  it("recupera uma resposta interrompida por recarregamento como cancelada", async () => {
    const row = await create();
    const stored = JSON.parse(values.get(storageKey)!);
    stored.conversations[0].messages.push({
      id: "interrupted",
      role: "assistant",
      content: "",
      status: "processing",
      created_at: row.created_at,
      sources: [],
    });
    values.set(storageKey, JSON.stringify(stored));
    vi.resetModules();
    const reloaded = await import("./adapter");
    const messages = await reloaded.request<RemoteMessage[]>(
      `/conversations/${row.id}/messages`,
    );
    expect(messages[0].status).toBe("cancelled");
  });
  it("seleciona adaptador local explicitamente e recusa autenticação", async () => {
    vi.stubEnv("DEV", true);
    vi.stubGlobal("__LOCAL_DEMO__", true);
    const client = await import("../api/client");
    expect(client.offline).toBe(true);
    expect(client.authConfigured).toBe(false);
    expect(await client.request("/me")).toMatchObject({ id: "demo-local" });
    await expect(client.requestCode("user@example.invalid")).rejects.toThrow(
      "indisponível",
    );
    await expect(
      client.verifyCode("user@example.invalid", "000000"),
    ).rejects.toThrow("indisponível");
  });
  it("não permite ativação em produção nem por padrão", async () => {
    vi.stubEnv("DEV", false);
    vi.stubGlobal("__LOCAL_DEMO__", true);
    expect((await import("../api/client")).offline).toBe(false);
    vi.resetModules();
    vi.stubEnv("DEV", true);
    vi.stubGlobal("__LOCAL_DEMO__", false);
    expect((await import("../api/client")).offline).toBe(false);
  });
});
