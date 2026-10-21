import type { Conversation, WorkspaceState, SupportAction } from "../types";
export type WorkspaceAction =
  | { type: "create"; id: string; now: string }
  | { type: "select"; id: string }
  | { type: "draft"; value: string }
  | { type: "rename"; id: string; title: string }
  | { type: "delete"; id: string }
  | {
      type: "send";
      id: string;
      messageId: string;
      now: string;
      content?: string;
      topicId?: string | null;
      questionId?: string;
      supportAction?: SupportAction;
    };
export function workspaceReducer(
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState {
  const active = state.conversations.find((c) => c.id === state.activeId);
  switch (action.type) {
    case "create":
      return {
        ...state,
        activeId: action.id,
        conversations: [
          {
            id: action.id,
            title: "Nova conversa",
            createdAt: action.now,
            updatedAt: action.now,
            draft: "",
            messages: [],
            references: [],
          },
          ...state.conversations,
        ],
      };
    case "select":
      return state.conversations.some((c) => c.id === action.id)
        ? { ...state, activeId: action.id }
        : state;
    case "draft":
      return active
        ? {
            ...state,
            conversations: state.conversations.map((c) =>
              c.id === active.id ? { ...c, draft: action.value } : c,
            ),
          }
        : { ...state, draft: action.value };
    case "rename":
      return action.title.trim()
        ? {
            ...state,
            conversations: state.conversations.map((c) =>
              c.id === action.id
                ? { ...c, title: action.title.trim().slice(0, 100) }
                : c,
            ),
          }
        : state;
    case "delete": {
      const remaining = state.conversations.filter((c) => c.id !== action.id);
      return {
        ...state,
        conversations: remaining,
        activeId:
          state.activeId === action.id
            ? (remaining[0]?.id ?? null)
            : state.activeId,
      };
    }
    case "send": {
      const content = (active?.draft ?? state.draft).trim();
      if (!content) return state;
      const message = {
        id: action.messageId,
        role: "user" as const,
        content,
        createdAt: action.now,
      };
      const conversation: Conversation = active
        ? {
            ...active,
            title:
              active.messages.length === 0 && active.title === "Nova conversa"
                ? content.slice(0, 64)
                : active.title,
            draft: "",
            updatedAt: action.now,
            messages: [...active.messages, message],
          }
        : {
            id: action.id,
            title: content.slice(0, 64),
            createdAt: action.now,
            updatedAt: action.now,
            draft: "",
            messages: [message],
            references: [],
          };
      return {
        ...state,
        activeId: conversation.id,
        draft: active ? state.draft : "",
        conversations: [
          conversation,
          ...state.conversations.filter((c) => c.id !== conversation.id),
        ],
      };
    }
  }
}
