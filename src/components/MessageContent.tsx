import { Fragment, type ReactNode } from "react";
import { safeLink } from "./safeLink";

// Deliberately limited Markdown: React escapes all text; HTML is never interpreted.
function inline(text: string, trustedLinks: string[]): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (link)
      return safeLink(link[2]) &&
        (trustedLinks.length === 0 || trustedLinks.includes(link[2])) ? (
        <a key={i} href={link[2]} target="_blank" rel="noopener noreferrer">
          {link[1]}
        </a>
      ) : (
        <Fragment key={i}>{link[1]}</Fragment>
      );
    return <Fragment key={i}>{part}</Fragment>;
  });
}
export function MessageContent({
  content,
  trustedLinks = [],
}: {
  content: string;
  trustedLinks?: string[];
}) {
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    if (!lines[index].trim()) {
      index++;
      continue;
    }
    const item = /^\s*(?:([-*+])|([0-9]+)[.)])\s+(.+)$/.exec(lines[index]);
    if (item) {
      const ordered = Boolean(item[2]);
      const items: ReactNode[] = [];
      const start = Number(item[2] || 1);
      while (index < lines.length) {
        const next = /^\s*(?:([-*+])|([0-9]+)[.)])\s+(.+)$/.exec(lines[index]);
        if (!next || Boolean(next[2]) !== ordered) break;
        items.push(<li key={index}>{inline(next[3], trustedLinks)}</li>);
        index++;
      }
      blocks.push(
        ordered ? (
          <ol key={index} start={start}>
            {items}
          </ol>
        ) : (
          <ul key={index}>{items}</ul>
        ),
      );
    } else {
      const paragraph: string[] = [];
      do {
        paragraph.push(lines[index++]);
      } while (
        index < lines.length &&
        lines[index].trim() &&
        !/^\s*(?:[-*+]|[0-9]+[.)])\s+/.test(lines[index])
      );
      blocks.push(
        <p key={index}>{inline(paragraph.join("\n"), trustedLinks)}</p>,
      );
    }
  }
  return <>{blocks}</>;
}
