import { useState } from "react";
import { authConfigured, requestCode, verifyCode } from "../api/client";
import shared from "./Shared.module.css";
export function SignIn() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!authConfigured)
    return (
      <p role="alert">O acesso precisa ser configurado pelo administrador.</p>
    );
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          if (sent) {
            await verifyCode(email, code);
            window.location.reload();
          } else {
            await requestCode(email);
            setSent(true);
          }
        } catch (error) {
          setError(
            error instanceof Error ? error.message : "Não foi possível entrar.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <p>Entre com seu e-mail corporativo.</p>
      <label className={shared.field}>
        E-mail
        <input
          type="email"
          autoComplete="email"
          required
          value={email}
          disabled={sent}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      {sent && (
        <label className={shared.field}>
          Código recebido por e-mail
          <input
            required
            autoComplete="one-time-code"
            inputMode="numeric"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </label>
      )}
      {error && <p role="alert">{error}</p>}
      <div className={shared.actions}>
        <button
          className={`${shared.button} ${shared.primary}`}
          disabled={busy}
        >
          {busy ? "Aguarde…" : sent ? "Entrar" : "Receber código"}
        </button>
      </div>
    </form>
  );
}
