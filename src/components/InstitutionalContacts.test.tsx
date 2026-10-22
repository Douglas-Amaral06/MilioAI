import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { InstitutionalContact } from "../types";
import { InstitutionalContacts } from "./InstitutionalContacts";
import { MessageContent } from "./MessageContent";

const contact: InstitutionalContact = {
  contact_id: "rh_frequency",
  team: "RH Frequência",
  domain: "folha_ponto",
  phone: "+55 11 97080-6028",
  phone_digits: "5511970806028",
  channel: "whatsapp",
  url: "https://wa.me/5511970806028",
  label: "WhatsApp da Frequência",
  email: "frequencia.sp@renapsi.org.br",
  email_url: "mailto:frequencia.sp@renapsi.org.br",
  validation_status: "pending_institutional",
  availability_status: "not_verified",
  provenance: {
    version: "folha-ponto-local-v1",
    directory_version: "1.0.0",
    institutionally_approved: false,
  },
};
describe("institutional contacts", () => {
  it("renders backend values, an accessible WhatsApp link and pending status", () => {
    const html = renderToStaticMarkup(
      <InstitutionalContacts contacts={[contact]} />,
    );
    expect(html).toContain('href="https://wa.me/5511970806028"');
    expect(html).toContain(
      'aria-label="WhatsApp da Frequência: +55 11 97080-6028"',
    );
    expect(html).toContain("ainda não confirmadas");
    expect(html).toContain("frequencia.sp@renapsi.org.br");
    expect(html).toContain("mailto:frequencia.sp@renapsi.org.br");
  });
  it.each([
    "https://wa.me/5511970806728",
    "https://wa.me.evil.test/5511970806028",
    "https://wa.me/5511970806028?text=nome",
    "javascript:alert(1)",
  ])("rejects manipulated destination %s", (url) => {
    expect(
      renderToStaticMarkup(
        <InstitutionalContacts contacts={[{ ...contact, url }]} />,
      ),
    ).not.toContain("href=");
  });
  it("does not promote generated links to institutional destinations", () => {
    for (const url of [
      contact.url,
      "https://evil.test",
      "https://conectajovem.dema.org.br@evil.test/",
    ]) {
      expect(
        renderToStaticMarkup(<MessageContent content={`[Contato](${url})`} />),
      ).not.toContain("href=");
    }
  });
  it("shows the supplied Atendimento phone without enabling WhatsApp", () => {
    const html = renderToStaticMarkup(
      <InstitutionalContacts
        contacts={[
          {
            ...contact,
            contact_id: "service",
            team: "Atendimento",
            phone: "+55 61 8606-0081",
            phone_digits: "556186060081",
            channel: "phone",
            whatsapp_enabled: false,
            url: null,
            email: "atendimento.sp@renapsi.org.br",
            email_url: "mailto:atendimento.sp@renapsi.org.br",
          },
        ]}
      />,
    );
    expect(html).toContain("+55 61 8606-0081");
    expect(html).toContain("WhatsApp pendente de confirmação");
    expect(html).not.toContain("wa.me");
  });
  it("has no invented contact when fields are absent", () => {
    expect(renderToStaticMarkup(<InstitutionalContacts />)).toBe("");
  });
});
