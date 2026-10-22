import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { InstitutionalContact } from "../types";
import { AssistantResponse, contactBody } from "./AssistantResponse";
const service: InstitutionalContact = {
  contact_id: "service",
  team: "Atendimento",
  domain: "beneficios",
  phone: "+55 61 8606-0081",
  phone_digits: "556186060081",
  channel: "phone",
  whatsapp_enabled: false,
  url: null,
  label: "Contato do Atendimento",
  email: "atendimento.sp@renapsi.org.br",
  email_url: "mailto:atendimento.sp@renapsi.org.br",
  validation_status: "pending_institutional",
  availability_status: "not_verified",
  provenance: {
    version: "2026-10-22",
    directory_version: "1.1.0",
    institutionally_approved: false,
  },
};
describe("single contact presentation", () => {
  it("shows contact values once in cards for new and historic messages", () => {
    const content =
      "Procure o Atendimento.\n\nTelefone informado: +55 61 8606-0081\nE-mail: atendimento.sp@renapsi.org.br";
    const html = renderToStaticMarkup(
      <AssistantResponse content={content} contacts={[service]} />,
    );
    const visible = html.replace(/<[^>]+>/g, "");
    expect(visible.split(service.phone)).toHaveLength(2);
    expect(visible.split(service.email)).toHaveLength(2);
    expect(visible).toContain("Procure o Atendimento");
    expect(visible).toContain("WhatsApp pendente");
    expect(html).not.toContain("wa.me");
  });
  it("retains rule conditions and operator contacts", () => {
    const body = contactBody(
      "Procure ajuda antes do prazo final. Telefone: +55 61 8606-0081. Ligue 156 para a operadora.",
      [service],
    );
    expect(body).toContain("antes do prazo final");
    expect(body).toContain("156");
    expect(body).not.toContain(service.phone);
  });
  it("does not suppress text using an invalid card", () => {
    expect(
      contactBody(service.phone, [{ ...service, phone_digits: "999" }]),
    ).toContain(service.phone);
  });
});
