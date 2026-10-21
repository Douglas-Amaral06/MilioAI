import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { WorkspaceState, SupportAction } from "../types";
import type { WorkspaceAction } from "../data/workspace";
import {
  allPages,
  ApiError,
  request,
  streamMessage,
  toConversation,
  toMessage,
  type Attachment,
  type RemoteConversation,
  type RemoteMessage,
  type SupportTopic,
} from "../api/client";
const initial: WorkspaceState = {
  version: 1,
  conversations: [],
  activeId: null,
  draft: "",
};
class FeedbackError extends Error {}
export function useWorkspace() {
  const [state, setState] = useState<WorkspaceState>(initial);
  const [storageError, setError] = useState("");
  const [needsLogin, setNeedsLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sendPhase, setSendPhase] = useState<"idle" | "sending" | "responding">(
    "idle",
  );
  const [initializing, setInitializing] = useState(true);
  const [topics, setTopics] = useState<SupportTopic[]>([]);
  const [selectingTopic, setSelectingTopic] = useState(false);
  const topicMutation = useRef(false);
  const [attachments, setAttachments] = useState<Record<string, Attachment[]>>(
    {},
  );
  const [uploading, setUploading] = useState(false);
  const stateRef = useRef(state);
  useLayoutEffect(() => {
    stateRef.current = state;
  }, [state]);
  const controller = useRef<AbortController | null>(null);
  const busyRef = useRef(false);
  const selectedVersion = useRef(0);
  const report = useCallback((error: unknown) => {
    if (error instanceof DOMException && error.name === "AbortError") return;
    if (error instanceof ApiError && error.status === 401) setNeedsLogin(true);
    setError(
      error instanceof FeedbackError
        ? error.message
        : error instanceof ApiError && error.status === 401
          ? "Sua sessão expirou. Acesse novamente para continuar."
          : error instanceof ApiError && error.status === 403
            ? "Você não tem permissão para realizar esta ação."
            : "Não foi possível concluir sua solicitação. Tente novamente.",
    );
  }, []);
  const refreshList = useCallback(async () => {
    const rows = await allPages<RemoteConversation>("/conversations");
    setState((previous) => ({
      ...previous,
      conversations: rows.map((row) => ({
        ...toConversation(row),
        ...previous.conversations.find((c) => c.id === row.id),
        title: row.title,
        updatedAt: row.updated_at,
        topicId: row.topic_id ?? null,
        supportState: row.support_state,
      })),
    }));
  }, []);
  const load = useCallback(async (id: string) => {
    const conversation = await request<RemoteConversation>(
      `/conversations/${id}`,
    );
    const messages = await allPages<RemoteMessage>(
      `/conversations/${id}/messages`,
    );
    const files = await allPages<Attachment>(
      `/conversations/${id}/attachments`,
    );
    setState((previous) => ({
      ...previous,
      conversations: previous.conversations.map((c) =>
        c.id === id
          ? {
              ...c,
              messages: messages.map(toMessage),
              supportState: conversation.support_state,
              topicId: conversation.topic_id,
            }
          : c,
      ),
    }));
    setAttachments((previous) => ({ ...previous, [id]: files }));
  }, []);
  useEffect(() => {
    let mounted = true;
    (async () => {
      await request("/me");
      const catalog = await request<SupportTopic[]>("/support/topics");
      if (mounted) setTopics(catalog);
      const rows = await allPages<RemoteConversation>("/conversations");
      if (!mounted) return;
      setNeedsLogin(false);
      setError("");
      setState({
        ...initial,
        conversations: rows.map(toConversation),
        activeId: rows[0]?.id ?? null,
      });
      if (rows[0]) await load(rows[0].id);
    })()
      .catch((error) => {
        if (mounted) report(error);
      })
      .finally(() => {
        if (mounted) setInitializing(false);
      });
    return () => {
      mounted = false;
      controller.current?.abort();
    };
  }, [load, report]);
  const active = state.conversations.find((c) => c.id === state.activeId);
  const waiting =
    active?.messages.some((m) => m.status === "processing") && !busy;
  useEffect(() => {
    if (!waiting || !state.activeId) return;
    const timer = window.setInterval(() => {
      load(state.activeId!).catch(report);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [waiting, state.activeId, load, report]);
  async function createConversation(draft = "") {
    const row = await request<RemoteConversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: "Nova conversa" }),
    });
    const conversation = { ...toConversation(row), draft };
    setState((previous) => ({
      ...previous,
      activeId: row.id,
      conversations: [conversation, ...previous.conversations],
    }));
    stateRef.current = {
      ...stateRef.current,
      activeId: row.id,
      conversations: [conversation, ...stateRef.current.conversations],
    };
    selectedVersion.current++;
    return row.id;
  }
  async function dispatch(action: WorkspaceAction) {
    if (action.type === "draft") {
      setState((previous) =>
        previous.activeId
          ? {
              ...previous,
              conversations: previous.conversations.map((c) =>
                c.id === previous.activeId ? { ...c, draft: action.value } : c,
              ),
            }
          : { ...previous, draft: action.value },
      );
      return true;
    }
    if (initializing) return false;
    try {
      setError("");
      switch (action.type) {
        case "create":
          if (busyRef.current || uploading || topicMutation.current)
            return false;
          busyRef.current = true;
          setBusy(true);
          try {
            await createConversation();
          } finally {
            busyRef.current = false;
            setBusy(false);
          }
          break;
        case "select": {
          if (busyRef.current || uploading) return;
          const version = ++selectedVersion.current;
          await load(action.id);
          if (version === selectedVersion.current)
            setState((previous) => ({ ...previous, activeId: action.id }));
          break;
        }
        case "rename":
          await request(`/conversations/${action.id}`, {
            method: "PATCH",
            body: JSON.stringify({ title: action.title }),
          });
          await refreshList();
          break;
        case "delete": {
          await request(`/conversations/${action.id}`, { method: "DELETE" });
          const next = stateRef.current.conversations.filter(
            (c) => c.id !== action.id,
          );
          const activeId =
            stateRef.current.activeId === action.id
              ? (next[0]?.id ?? null)
              : stateRef.current.activeId;
          setState((previous) => ({
            ...previous,
            conversations: next,
            activeId,
          }));
          if (activeId) await load(activeId);
          break;
        }
        case "send": {
          if (busyRef.current || uploading || topicMutation.current) return;
          const current = stateRef.current;
          const text = (
            action.content ??
            current.conversations.find((c) => c.id === current.activeId)
              ?.draft ??
            current.draft
          ).trim();
          if (!text && !action.supportAction) return;
          busyRef.current = true;
          setBusy(true);
          let cid = current.activeId;
          setSendPhase("sending");
          let assistantId = "";
          try {
            cid ??= await createConversation(
              action.supportAction || action.questionId ? "" : current.draft,
            );
            const target = cid;
            controller.current = new AbortController();
            const fileIds = (attachments[cid] ?? [])
              .filter((f) => !f.message_id)
              .map((f) => f.id);
            await streamMessage(
              cid,
              {
                request_id: action.messageId,
                content:
                  action.questionId || action.supportAction ? undefined : text,
                action: action.supportAction,
                topic_id:
                  action.topicId ??
                  current.conversations.find((c) => c.id === current.activeId)
                    ?.topicId ??
                  null,
                question_id: action.questionId,
                attachment_ids: action.supportAction ? [] : fileIds,
              },
              controller.current.signal,
              (event) => {
                if (event.event === "error") {
                  setError(
                    "Não foi possível concluir a resposta. Você pode enviar uma nova mensagem.",
                  );
                  setState((previous) => ({
                    ...previous,
                    conversations: previous.conversations.map((c) =>
                      c.id !== target
                        ? c
                        : {
                            ...c,
                            messages: c.messages.map((m) =>
                              m.id === assistantId
                                ? { ...m, status: "failed" }
                                : m,
                            ),
                          },
                    ),
                  }));
                  return;
                }
                if (event.event === "start") setSendPhase("responding");
                setState((previous) => ({
                  ...previous,
                  draft:
                    event.event === "start" && !action.supportAction
                      ? ""
                      : previous.draft,
                  conversations: previous.conversations.map((c) => {
                    if (c.id !== target) return c;
                    if (event.event === "start") {
                      assistantId = event.assistant.id;
                      return {
                        ...c,
                        draft: action.supportAction ? c.draft : "",
                        messages: [
                          ...c.messages,
                          toMessage(event.user),
                          toMessage(event.assistant),
                        ],
                      };
                    }
                    return {
                      ...c,
                      messages: c.messages.map((m) =>
                        m.id === assistantId
                          ? event.event === "delta"
                            ? { ...m, content: m.content + event.text }
                            : event.event === "sources"
                              ? { ...m, sources: event.sources }
                              : event.event === "done"
                                ? toMessage(event.message)
                                : m
                          : m,
                      ),
                    };
                  }),
                }));
              },
            );
          } catch (error) {
            if (assistantId)
              setState((previous) => ({
                ...previous,
                conversations: previous.conversations.map((c) =>
                  c.id !== cid
                    ? c
                    : {
                        ...c,
                        messages: c.messages.map((m) =>
                          m.id === assistantId ? { ...m, status: "failed" } : m,
                        ),
                      },
                ),
              }));
            throw error;
          } finally {
            controller.current = null;
            try {
              if (cid) {
                await load(cid);
                await refreshList();
              }
            } finally {
              busyRef.current = false;
              setBusy(false);
              setSendPhase("idle");
            }
          }
          break;
        }
      }
    } catch (error) {
      report(error);
      return false;
    }
    return true;
  }
  async function selectTopic(id: string | null) {
    if (busyRef.current || topicMutation.current || uploading) return;
    topicMutation.current = true;
    setSelectingTopic(true);
    setError("");
    try {
      const cid = stateRef.current.activeId ?? (await createConversation());
      const row = await request<RemoteConversation>(
        `/conversations/${cid}/topic`,
        { method: "PATCH", body: JSON.stringify({ topic_id: id }) },
      );
      setState((previous) => ({
        ...previous,
        conversations: previous.conversations.map((c) =>
          c.id === cid
            ? {
                ...c,
                topicId: row.topic_id ?? null,
                supportState: row.support_state,
              }
            : c,
        ),
      }));
    } catch (error) {
      report(error);
    } finally {
      topicMutation.current = false;
      setSelectingTopic(false);
    }
  }
  async function sendGuided(
    topicId: string,
    questionId: string,
    content: string,
  ) {
    return dispatch({
      type: "send",
      id: crypto.randomUUID(),
      messageId: crypto.randomUUID(),
      now: new Date().toISOString(),
      topicId,
      questionId,
      content,
    });
  }
  async function upload(file: File) {
    if (uploading || busyRef.current) return;
    if (file.size > 5 * 1024 * 1024) {
      setError("O arquivo excede o limite de 5 MB.");
      return;
    }
    if (!/\.(pdf|txt|md)$/i.test(file.name)) {
      setError("Selecione um PDF, TXT ou Markdown.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const cid = stateRef.current.activeId ?? (await createConversation());
      if ((attachments[cid] ?? []).filter((f) => !f.message_id).length >= 5)
        throw new FeedbackError("Envie no máximo cinco anexos por mensagem.");
      const data = new FormData();
      data.append("file", file);
      const result = await request<Attachment>(
        `/conversations/${cid}/attachments`,
        { method: "POST", body: data },
      );
      setAttachments((previous) => ({
        ...previous,
        [cid]: [...(previous[cid] ?? []), result],
      }));
    } catch (error) {
      report(error);
    } finally {
      setUploading(false);
    }
  }
  async function removeAttachment(id: string) {
    const cid = stateRef.current.activeId;
    if (!cid) return;
    try {
      await request(`/conversations/${cid}/attachments/${id}`, {
        method: "DELETE",
      });
      setAttachments((previous) => ({
        ...previous,
        [cid]: (previous[cid] ?? []).filter((f) => f.id !== id),
      }));
    } catch (error) {
      report(error);
    }
  }
  return {
    cancelProcessing: () => controller.current?.abort(),
    sendPhase,
    state,
    dispatch,
    storageError,
    topics,
    selectTopic,
    sendGuided,
    sendSupportAction: (supportAction: SupportAction) =>
      dispatch({
        type: "send",
        id: crypto.randomUUID(),
        messageId: crypto.randomUUID(),
        now: new Date().toISOString(),
        content: "",
        supportAction,
      }),
    selectingTopic,
    needsLogin,
    busy: busy || initializing,
    uploading,
    upload,
    removeAttachment,
    attachments: attachments[state.activeId ?? ""] ?? [],
    active: state.conversations.find((c) => c.id === state.activeId),
  };
}
