import {
  ApiError,
  type RemoteConversation,
  type RemoteMessage,
  type StreamEvent,
} from "../api/remote";
import type { SupportAction } from "../types";
import {
  topics,
  instructors,
  cards,
  scenarios,
  sources,
  type Scenario,
} from "./fixtures";
export const storageKey = "milioai.demo.offline.v1";
interface Row extends RemoteConversation {
  messages: RemoteMessage[];
}
interface Database {
  version: 1;
  conversations: Row[];
}
let scenario: Scenario = "success";
let recovered = false;
export function setScenario(value: Scenario) {
  scenario = value;
}
function read(): Database {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return { version: 1, conversations: [] };
  try {
    const value = JSON.parse(raw) as Database;
    if (
      value.version !== 1 ||
      !Array.isArray(value.conversations) ||
      value.conversations.some((c) => !c.id || !Array.isArray(c.messages))
    )
      throw new Error();
    if (!recovered) {
      recovered = true;
      let changed = false;
      for (const row of value.conversations)
        for (const message of row.messages) {
          if (message.status === "processing") {
            message.status = "cancelled";
            changed = true;
          }
        }
      if (changed) save(value);
    }
    return value;
  } catch {
    throw new Error("Dados demonstrativos inválidos. Use Limpar demonstração.");
  }
}
function save(db: Database) {
  localStorage.setItem(storageKey, JSON.stringify(db));
}
export function resetDemo() {
  localStorage.removeItem(storageKey);
}
const copy = <T>(value: T): T => structuredClone(value);
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  options.signal?.throwIfAborted();
  const url = new URL(path, "http://demo.invalid");
  const parts = url.pathname.split("/").filter(Boolean);
  const method = options.method ?? "GET";
  const body = typeof options.body === "string" ? JSON.parse(options.body) : {};
  const paginate = <V>(values: V[]) =>
    values.slice(
      Number(url.searchParams.get("offset") ?? 0),
      Number(url.searchParams.get("offset") ?? 0) +
        Number(url.searchParams.get("limit") ?? 100),
    );
  let result: unknown;
  if (method === "GET" && path === "/me")
    result = {
      id: "demo-local",
      name: "Visitante de demonstração",
      email: "visitante@example.invalid",
    };
  else if (method === "GET" && path === "/support/topics") result = topics;
  else if (method === "GET" && path === "/support/instructors")
    result = instructors.map(({ id, name }) => ({ id, name }));
  else if (method === "GET" && path === "/support/transport-cards")
    result = cards;
  else if (parts[0] === "conversations") {
    const db = read();
    if (parts.length === 1 && method === "GET")
      result = paginate(db.conversations);
    else if (parts.length === 1 && method === "POST") {
      const now = new Date().toISOString();
      const row: Row = {
        id: crypto.randomUUID(),
        title: body.title || "Nova conversa",
        created_at: now,
        updated_at: now,
        topic_id: null,
        support_state: {},
        messages: [],
      };
      db.conversations.unshift(row);
      save(db);
      result = row;
    } else {
      const row = db.conversations.find((c) => c.id === parts[1]);
      if (!row)
        throw new ApiError(404, "Conversa demonstrativa não encontrada.");
      if (parts.length === 2 && method === "GET") result = row;
      else if (parts.length === 2 && method === "PATCH") {
        row.title = String(body.title).trim();
        row.updated_at = new Date().toISOString();
        save(db);
        result = row;
      } else if (parts.length === 2 && method === "DELETE") {
        db.conversations = db.conversations.filter((c) => c.id !== row.id);
        save(db);
      } else if (parts[2] === "messages" && method === "GET")
        result = paginate(row.messages);
      else if (parts[2] === "attachments") {
        if (method !== "GET")
          throw new ApiError(
            422,
            "Upload real indisponível na demonstração local. Nenhum arquivo foi enviado ou armazenado.",
          );
        result = [];
      } else if (parts[2] === "topic" && method === "PATCH") {
        if (
          body.topic_id !== null &&
          !topics.some((t) => t.topic_id === body.topic_id)
        )
          throw new ApiError(422, "Assunto inválido.");
        row.topic_id = body.topic_id;
        row.support_state = {};
        save(db);
        result = row;
      } else
        throw new ApiError(404, "Operação indisponível na demonstração local.");
    }
  } else
    throw new ApiError(404, "Operação indisponível na demonstração local.");
  return copy(result) as T;
}
function pause(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    signal.throwIfAborted();
    const abort = () => {
      clearTimeout(timer);
      reject(new DOMException("Processamento cancelado", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal.removeEventListener("abort", abort);
      resolve();
    }, ms);
    signal.addEventListener("abort", abort, { once: true });
  });
}
export async function streamMessage(
  cid: string,
  payload: object,
  signal: AbortSignal,
  onEvent: (event: StreamEvent) => void,
) {
  signal.throwIfAborted();
  const selectedScenario = scenario;
  const data = payload as {
    content?: string;
    topic_id?: string;
    question_id?: string;
    action?: SupportAction;
  };
  const db = read();
  const row = db.conversations.find((c) => c.id === cid);
  if (!row) throw new ApiError(404, "Conversa demonstrativa não encontrada.");
  const question = topics
    .find((t) => t.topic_id === data.topic_id)
    ?.questions.find((q) => q.question_id === data.question_id);
  if (data.question_id && !question)
    throw new ApiError(422, "Pergunta inválida.");
  const now = new Date().toISOString();
  const make = (
    role: RemoteMessage["role"],
    content: string,
    status: RemoteMessage["status"],
  ): RemoteMessage => ({
    id: crypto.randomUUID(),
    role,
    content,
    status,
    created_at: now,
    sources: [],
    topic_id: data.topic_id ?? row.topic_id,
    question_id: data.question_id,
  });
  const user = make(
    "user",
    question?.text ?? data.content ?? "Ação demonstrativa",
    "complete",
  );
  const assistant = make("assistant", "", "processing");
  let text = scenarios[selectedScenario];
  const action = data.action;
  const state = (row.support_state ??= {});
  if (action?.kind === "card_select") {
    const card = cards.find((c) => c.code === action.benefit_code);
    if (!card) throw new ApiError(422, "Cartão demonstrativo inválido.");
    state.vt_stage = "active";
    state.selected_card_code = card.code;
    text = `${card.name}: exemplo ilustrativo de seleção. Nenhuma solicitação de segunda via foi realizada.`;
  } else if (action?.kind === "card_change") {
    state.vt_stage = "selection";
    delete state.selected_card_code;
    text = "Escolha outro cartão demonstrativo.";
  } else if (action?.kind === "instructor_select") {
    const instructor = instructors.find((i) => i.id === action.instructor_id);
    if (!instructor)
      throw new ApiError(422, "Instrutor demonstrativo inválido.");
    state.stage = "contact";
    state.selected_instructor_id = instructor.id;
    text = instructor.contact
      ? `${instructor.name}: contato fictício ${instructor.contact}. Não utilize para atendimento real.`
      : `${instructor.name}: contato não informado neste exemplo.`;
  } else if (
    action?.kind === "instructor_known" ||
    action?.kind === "instructor_unknown" ||
    action?.kind === "instructor_resume"
  ) {
    state.asked = true;
    state.stage = "selection";
    text = "Selecione um instrutor fictício para explorar o fluxo.";
  } else if (action?.kind === "instructor_cancel") {
    state.stage = "idle";
    text = "Seleção demonstrativa cancelada. Você pode voltar à lista.";
  } else if (data.topic_id === "vale_transporte") {
    state.vt_stage = "selection";
    text = "Escolha um cartão fictício para explorar a interface.";
  } else if (
    data.topic_id === "falta_curso" ||
    data.question_id === "atestados.curso"
  ) {
    state.asked = true;
    state.stage = "confirmation";
    text =
      "Você sabe quem é seu instrutor? Os nomes e contatos deste fluxo são fictícios.";
  }
  text = `**Conteúdo demonstrativo — sem validade institucional.**\n\n${text}`;
  row.messages.push(user, assistant);
  row.updated_at = now;
  save(db);
  onEvent({ event: "start", user: copy(user), assistant: copy(assistant) });
  try {
    const chunks = text.match(/[\s\S]{1,80}/g) ?? [];
    for (const chunk of chunks) {
      await pause(selectedScenario === "slow" ? 500 : 25, signal);
      if (selectedScenario === "error") {
        assistant.status = "failed";
        assistant.content = scenarios.error;
        save(db);
        onEvent({
          event: "error",
          message: scenarios.error,
          code: "demo_failure",
        });
        return;
      }
      assistant.content += chunk;
      onEvent({ event: "delta", text: chunk });
    }
    if (selectedScenario === "sources") {
      assistant.sources = copy(sources);
      onEvent({ event: "sources", sources: copy(sources) });
    }
    assistant.status = "complete";
    save(db);
    onEvent({ event: "done", message: copy(assistant) });
  } catch (error) {
    assistant.status = signal.aborted ? "cancelled" : "failed";
    save(db);
    if (!signal.aborted) throw error;
  }
}
