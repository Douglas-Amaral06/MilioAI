import type { InstitutionalContact } from "../types";

function trustedContact(contact: InstitutionalContact): boolean {
  if (!/^[1-9]\d{7,14}$/.test(contact.phone_digits)) return false;
  if (contact.phone.replace(/\D/g, "") !== contact.phone_digits) return false;
  return (
    ((contact.channel === "whatsapp" &&
      contact.whatsapp_enabled !== false &&
      contact.url === `https://wa.me/${contact.phone_digits}`) ||
      (contact.channel === "phone" &&
        contact.whatsapp_enabled === false &&
        contact.url === null)) &&
    Boolean(
      contact.provenance?.version && contact.provenance?.directory_version,
    )
  );
}

export function InstitutionalContacts({
  contacts = [],
}: {
  contacts?: InstitutionalContact[];
}) {
  return (
    <>
      {contacts.filter(trustedContact).map((contact, index) => (
        <p key={`${contact.contact_id}-${index}`}>
          {contact.channel === "whatsapp" && contact.url ? (
            <a
              href={contact.url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${contact.label}: ${contact.phone}`}
            >
              {contact.label}
            </a>
          ) : (
            <span>{contact.team}</span>
          )}
          {" · "}
          {contact.phone}
          {contact.email_url === `mailto:${contact.email}` &&
          /^[a-zA-Z0-9._+-]+@renapsi\.org\.br$/.test(contact.email) ? (
            <>
              {" "}
              · <a href={contact.email_url}>{contact.email}</a>
            </>
          ) : (
            <> · {contact.email}</>
          )}
          {contact.whatsapp_enabled === false && (
            <small> · WhatsApp pendente de confirmação.</small>
          )}
          {contact.validation_status !== "validated" && (
            <>
              <br />
              <small>
                Contato para revisão local; vigência e disponibilidade ainda não
                confirmadas.
              </small>
            </>
          )}
        </p>
      ))}
    </>
  );
}
