import * as remote from "./remote";
export type {
  Attachment,
  RemoteConversation,
  RemoteMessage,
  SupportTopic,
  SupportQuestion,
  StreamEvent,
} from "./remote";
export { ApiError, toConversation, toMessage } from "./remote";

export const offline =
  import.meta.env.DEV &&
  typeof __LOCAL_DEMO__ !== "undefined" &&
  __LOCAL_DEMO__;
export const authConfigured = !offline && remote.authConfigured;
const adapter = () =>
  offline ? import("../offline/adapter") : Promise.resolve(remote);
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return (await adapter()).request<T>(path, options);
}
export async function streamMessage(
  ...args: Parameters<typeof remote.streamMessage>
) {
  return (await adapter()).streamMessage(...args);
}
export async function allPages<T>(path: string): Promise<T[]> {
  const rows: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<T[]>(`${path}?limit=100&offset=${offset}`);
    rows.push(...page);
    if (page.length < 100) return rows;
  }
}
export async function requestCode(email: string) {
  if (offline)
    throw new Error("Autenticação indisponível na demonstração local.");
  return remote.requestCode(email);
}
export async function verifyCode(email: string, token: string) {
  if (offline)
    throw new Error("Autenticação indisponível na demonstração local.");
  return remote.verifyCode(email, token);
}
export function logout() {
  if (!offline) remote.logout();
}
