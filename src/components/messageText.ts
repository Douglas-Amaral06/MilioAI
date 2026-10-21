import { safeLink } from "./safeLink";

// These internal citations are also omitted from the visible message body.
export const visibleMessageText = (content: string) =>
  content.replace(/\[fonte:[^\]]*(?:\]|$)/g, "");

// Keep paragraph breaks and list markers, using the same limited inline Markdown
// syntax as MessageContent. Links written in the answer retain their destination.
export function clipboardMessageText(content: string) {
  return visibleMessageText(content)
    .replace(/\r\n?/g, "\n")
    .replace(
      /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)/g,
      (_, bold: string | undefined, label: string, url: string) =>
        bold ?? (safeLink(url) ? `${label} (${url})` : label),
    );
}
