import type { Conversation, Message } from "../types";
const base = "/api/v1";
const sessionKey = "milioai.auth.session.v1";
interface Session {
  access_token: string;
  refresh_token: string;
  expires_at: number;
}
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const publishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as
  string | undefined;
export const authConfigured = Boolean(supabaseUrl && publishableKey);
let refreshing: Promise<Session> | null = null;
function loadSession(): Session | null {
  try {
    return JSON.parse(sessionStorage.getItem(sessionKey) || "null");
  } catch {
    return null;
  }
}
function saveSession(value: Session) {
  sessionStorage.setItem(sessionKey, JSON.stringify(value));
}
export function logout() {
  sessionStorage.removeItem(sessionKey);
  window.location.reload();
}
async function authRequest(path: string, body: object) {
  if (!authConfigured)
    throw new Error(
      "O acesso corporativo precisa ser configurado pelo administrador.",
    );
  const result = await fetch(`${supabaseUrl}/auth/v1/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: publishableKey! },
    body: JSON.stringify(body),
  });
  if (!result.ok)
    throw new Error(
      "Não foi possível validar o acesso. Confira os dados e tente novamente.",
    );
  return result.json();
}
export async function requestCode(email: string) {
  await authRequest("otp", { email, create_user: false });
}
export async function verifyCode(email: string, token: string) {
  const result = await authRequest("verify", { email, token, type: "email" });
  saveSession({ ...result, expires_at: Date.now() / 1000 + result.expires_in });
}
async function authHeaders(): Promise<Record<string, string>> {
  let session = loadSession();
  if (session && session.expires_at < Date.now() / 1000 + 30) {
    refreshing ??= authRequest("token?grant_type=refresh_token", {
      refresh_token: session.refresh_token,
    })
      .then((result) => {
        const value = {
          ...result,
          expires_at: Date.now() / 1000 + result.expires_in,
        };
        saveSession(value);
        return value;
      })
      .finally(() => {
        refreshing = null;
      });
    session = await refreshing;
  }
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(base + path, {
    ...options,
    headers: {
      ...(await authHeaders()),
      ...(options.body instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.message || "Não foi possível conectar ao serviço.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export interface SupportQuestion {
  question_id: string;
  topic_id: string;
  text: string;
  ordering: number;
  enabled: boolean;
}
export interface SupportTopic {
  topic_id: string;
  title: string;
  description?: string;
  domain: string;
  agent_id: string | null;
  ordering: number;
  enabled: boolean;
  questions: SupportQuestion[];
}
export interface RemoteConversation {
  support_state?: Conversation["supportState"];
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  topic_id?: string | null;
}
export interface RemoteMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: Message["status"];
  created_at: string;
  sources: NonNullable<Message["sources"]>;
  outcome?: string;
  topic_id?: string | null;
  question_id?: string | null;
}
export interface Attachment {
  id: string;
  name: string;
  size: number;
  status: string;
  message_id?: string;
}
export const toConversation = (c: RemoteConversation): Conversation => ({
  id: c.id,
  title: c.title,
  createdAt: c.created_at,
  updatedAt: c.updated_at,
  draft: "",
  messages: [],
  references: [],
  topicId: c.topic_id ?? null,
  supportState: c.support_state,
});
export const toMessage = (m: RemoteMessage): Message => ({
  id: m.id,
  role: m.role,
  content: m.content,
  createdAt: m.created_at,
  status: m.status,
  sources: m.sources,
  outcome: m.outcome,
  topicId: m.topic_id,
  questionId: m.question_id,
});
export async function allPages<T>(path: string): Promise<T[]> {
  const values: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<T[]>(`${path}?limit=100&offset=${offset}`);
    values.push(...page);
    if (page.length < 100) return values;
  }
}
export async function streamMessage(
  cid: string,
  payload: object,
  signal: AbortSignal,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(`${base}/conversations/${cid}/stream`, {
    method: "POST",
    headers: { ...(await authHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      error?.message || "Não foi possível enviar a mensagem.",
    );
  }
  if (!response.body) throw new Error("A conexão foi interrompida.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "",
    terminal = false;
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
      let boundary;
      while ((boundary = buffer.indexOf("\n\n")) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (data) {
          const event = JSON.parse(data) as StreamEvent;
          onEvent(event);
          if (event.event === "done" || event.event === "error")
            terminal = true;
        }
      }
      if (done) break;
    }
    if (!terminal)
      throw new Error(
        "A resposta foi interrompida. O histórico será atualizado.",
      );
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
export type StreamEvent =
  | { event: "start"; user: RemoteMessage; assistant: RemoteMessage }
  | { event: "delta"; text: string }
  | { event: "sources"; sources: NonNullable<Message["sources"]> }
  | { event: "done"; message: RemoteMessage }
  | { event: "error"; message: string; code: string };
