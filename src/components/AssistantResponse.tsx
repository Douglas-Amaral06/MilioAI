import type { InstitutionalContact } from "../types";
import { MessageContent } from "./MessageContent";
import { InstitutionalContacts, trustedContact } from "./InstitutionalContacts";

export function contactBody(
  content: string,
  contacts: InstitutionalContact[] = [],
): string {
  let body = content;
  for (const contact of contacts.filter(trustedContact)) {
    const values = [
      contact.phone,
      contact.phone.replace(/^\+55 /, ""),
      contact.email,
      contact.url,
    ].filter((value): value is string => Boolean(value));
    for (const value of values) {
      const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      body = body.replace(
        new RegExp(`\\[[^\\]]*\\]\\((?:mailto:)?${escaped}\\)`, "g"),
        "",
      );
      body = body.split(value).join("");
    }
  }
  if (contacts.length) {
    body = body.replace(
      /(?:telefone(?: informado)?|e-mail|whatsapp|celular)\s*:\s*(?=ou\b|[.\n]|\[fonte:|$)/gi,
      "",
    );
    body = body.replace(/\bou\s+(?=whatsapp\s*:\s*(?:\[fonte:|$))/gi, "");
    body = body.replace(/whatsapp\s*:\s*(?=\[fonte:|$)/gi, "");
    body = body
      .replace(/^\s*(?:ou|[·.,;:]|\[fonte:[^\]]+\])?\s*$/gm, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }
  return body;
}

export function AssistantResponse({
  content,
  contacts = [],
}: {
  content: string;
  contacts?: InstitutionalContact[];
}) {
  return (
    <>
      <MessageContent content={contactBody(content, contacts)} />
      <InstitutionalContacts contacts={contacts} />
    </>
  );
}
