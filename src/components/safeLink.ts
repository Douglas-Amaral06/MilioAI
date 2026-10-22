import policy from "../../backend/app/support/link_policy.json";

export function safeLink(value: string): boolean {
  if (/\s/.test(value) || Array.from(value).some((c) => c.charCodeAt(0) < 32))
    return false;
  if (value.startsWith("mailto:"))
    return /^[a-zA-Z0-9._+-]+@renapsi\.org\.br$/.test(value.slice(7));
  // Team telephone/WhatsApp links use the structured contact component.
  if (value.startsWith("tel:")) return false;
  try {
    const url = new URL(value);
    return (
      url.protocol === "https:" &&
      policy.https_hosts.includes(url.hostname) &&
      !url.username &&
      !url.password &&
      !url.port
    );
  } catch {
    return false;
  }
}
