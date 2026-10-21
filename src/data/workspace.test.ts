import { describe, expect, it } from "vitest";
import { workspaceReducer } from "./workspace";
import { createLocalRepository, emptyWorkspace, STORAGE_KEY } from "./storage";
const now = "2026-10-15T12:00:00.000Z";
const create = (state = emptyWorkspace(), id = "a") =>
  workspaceReducer(state, { type: "create", id, now });
describe("conversas locais", () => {
  it("envia sem fabricar resposta e restaura mensagens e rascunhos", () => {
    let state = workspaceReducer(emptyWorkspace(), {
      type: "draft",
      value: "Como envio um atestado?",
    });
    state = workspaceReducer(state, {
      type: "send",
      id: "a",
      messageId: "m1",
      now,
    });
    expect(state.conversations[0].messages).toHaveLength(1);
    expect(state.conversations[0].messages[0].role).toBe("user");
    expect(state.conversations[0].title).toBe("Como envio um atestado?");
    state = workspaceReducer(state, {
      type: "draft",
      value: "Rascunho\ncom duas linhas",
    });
    const data = new Map<string, string>();
    const repo = createLocalRepository({
      getItem: (key) => data.get(key) ?? null,
      setItem: (key, value) => {
        data.set(key, value);
      },
    });
    expect(repo.save(state)).toBe(true);
    expect(repo.load().state).toEqual(state);
  });
  it("mantém rascunhos independentes ao criar e alternar conversas", () => {
    let state = workspaceReducer(create(), {
      type: "draft",
      value: "Rascunho A",
    });
    state = create(state, "b");
    state = workspaceReducer(state, { type: "draft", value: "Rascunho B" });
    state = workspaceReducer(state, { type: "select", id: "a" });
    expect(state.activeId).toBe("a");
    expect(state.conversations.find((c) => c.id === "a")?.draft).toBe(
      "Rascunho A",
    );
    expect(state.conversations.find((c) => c.id === "b")?.draft).toBe(
      "Rascunho B",
    );
  });
  it("rejeita envio vazio e preserva título renomeado no primeiro envio", () => {
    let state = create();
    expect(
      workspaceReducer(state, { type: "send", id: "x", messageId: "m", now }),
    ).toBe(state);
    state = workspaceReducer(state, {
      type: "rename",
      id: "a",
      title: "  Minha conversa  ",
    });
    state = workspaceReducer(state, { type: "draft", value: "  Pergunta  " });
    state = workspaceReducer(state, {
      type: "send",
      id: "x",
      messageId: "m",
      now,
    });
    expect(state.conversations[0].title).toBe("Minha conversa");
    expect(state.conversations[0].messages[0].content).toBe("Pergunta");
  });
  it("seleciona conversa restante ao excluir a ativa e retorna ao estado vazio", () => {
    const state = workspaceReducer(create(create(), "b"), {
      type: "delete",
      id: "b",
    });
    expect(state.activeId).toBe("a");
    expect(
      workspaceReducer(state, { type: "delete", id: "a" }).activeId,
    ).toBeNull();
  });
});
describe("persistência", () => {
  it("recupera-se de dados corrompidos ou contratos inválidos", () => {
    for (const raw of [
      "{",
      JSON.stringify({ ...emptyWorkspace(), conversations: [{ id: "a" }] }),
    ]) {
      const result = createLocalRepository({
        getItem: () => raw,
        setItem: () => {},
      }).load();
      expect(result.state).toEqual(emptyWorkspace());
      expect(result.error).toBeTruthy();
    }
  });
  it("informa quota ou acesso indisponível sem derrubar a aplicação", () => {
    const repo = createLocalRepository({
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("quota");
      },
    });
    expect(repo.load().error).toBeTruthy();
    expect(repo.save(emptyWorkspace())).toBe(false);
  });
  it("ignora seleção que não existe e rejeita identificadores duplicados", () => {
    const state = create();
    const repo = (value: unknown) =>
      createLocalRepository({
        getItem: (key) => (key === STORAGE_KEY ? JSON.stringify(value) : null),
        setItem: () => {},
      });
    expect(
      repo({ ...state, activeId: "missing" }).load().state.activeId,
    ).toBeNull();
    expect(
      repo({
        ...state,
        conversations: [...state.conversations, ...state.conversations],
      }).load().error,
    ).toBeTruthy();
  });
});
