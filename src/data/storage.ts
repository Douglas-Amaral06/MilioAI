import type { Conversation, WorkspaceState } from "../types";
export const STORAGE_KEY = "milioai.workspace.v1";
export const emptyWorkspace = (): WorkspaceState => ({
  version: 1,
  conversations: [],
  activeId: null,
  draft: "",
});
export interface WorkspaceRepository {
  load(): { state: WorkspaceState; error?: string };
  save(state: WorkspaceState): boolean;
}
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;
const isDate = (value: unknown): value is string =>
  typeof value === "string" && Number.isFinite(Date.parse(value));
function isConversation(value: unknown): value is Conversation {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.draft === "string" &&
    isDate(value.createdAt) &&
    isDate(value.updatedAt) &&
    Array.isArray(value.messages) &&
    value.messages.every(
      (m) =>
        isRecord(m) &&
        typeof m.id === "string" &&
        m.role === "user" &&
        typeof m.content === "string" &&
        isDate(m.createdAt),
    ) &&
    Array.isArray(value.references) &&
    value.references.every(
      (r) =>
        isRecord(r) &&
        typeof r.id === "string" &&
        typeof r.title === "string" &&
        (r.url === undefined || typeof r.url === "string") &&
        (r.excerpt === undefined || typeof r.excerpt === "string"),
    )
  );
}
export function createLocalRepository(
  storage: Pick<Storage, "getItem" | "setItem">,
): WorkspaceRepository {
  return {
    load() {
      try {
        const raw = storage.getItem(STORAGE_KEY);
        if (!raw) return { state: emptyWorkspace() };
        const data: unknown = JSON.parse(raw);
        if (
          !isRecord(data) ||
          data.version !== 1 ||
          !Array.isArray(data.conversations) ||
          !data.conversations.every(isConversation) ||
          typeof data.draft !== "string" ||
          !(data.activeId === null || typeof data.activeId === "string") ||
          new Set(data.conversations.map((c) => c.id)).size !==
            data.conversations.length
        )
          throw new Error("Invalid data");
        return {
          state: {
            version: 1,
            conversations: data.conversations,
            draft: data.draft,
            activeId: data.conversations.some((c) => c.id === data.activeId)
              ? data.activeId
              : null,
          },
        };
      } catch {
        return {
          state: emptyWorkspace(),
          error:
            "Não foi possível restaurar o histórico local. Você pode continuar nesta sessão.",
        };
      }
    },
    save(state) {
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify(state));
        return true;
      } catch {
        return false;
      }
    },
  };
}
export const localRepository: WorkspaceRepository = {
  load() {
    try {
      return createLocalRepository(window.localStorage).load();
    } catch {
      return {
        state: emptyWorkspace(),
        error:
          "Armazenamento local indisponível. As conversas durarão apenas nesta sessão.",
      };
    }
  },
  save(state) {
    try {
      return createLocalRepository(window.localStorage).save(state);
    } catch {
      return false;
    }
  },
};
