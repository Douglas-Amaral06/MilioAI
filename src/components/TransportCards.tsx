import { useEffect, useId, useState } from "react";
import { request } from "../api/client";
import type { SupportAction, SupportState } from "../types";
import s from "./Chat.module.css";
type Card = { code: string; name: string; uf: string };
const normalize = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("pt-BR");
function CardPicker({
  busy,
  onAction,
}: {
  busy: boolean;
  onAction: (action: SupportAction) => void;
}) {
  const [rows, setRows] = useState<Card[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const id = useId();
  useEffect(() => {
    const abort = new AbortController();
    request<Card[]>("/support/transport-cards", { signal: abort.signal })
      .then((value) => {
        if (!abort.signal.aborted) setRows(value);
      })
      .catch(() => {
        if (!abort.signal.aborted)
          setError("Não foi possível carregar os cartões. Tente novamente.");
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoaded(true);
      });
    return () => abort.abort();
  }, [attempt]);
  const filtered = rows.filter((card) =>
    normalize(`${card.name} ${card.code} ${card.uf}`).includes(
      normalize(search),
    ),
  );
  return (
    <>
      <label htmlFor={id}>Buscar cartão ou operadora</label>
      <input
        id={id}
        type="search"
        value={search}
        disabled={busy}
        onChange={(event) => setSearch(event.target.value)}
        autoComplete="off"
      />
      {!loaded && <p role="status">Carregando cartões…</p>}
      {error && (
        <p role="alert">
          {error}{" "}
          <button
            disabled={busy}
            onClick={() => {
              setError("");
              setLoaded(false);
              setAttempt((value) => value + 1);
            }}
          >
            Tentar novamente
          </button>
        </p>
      )}
      {loaded && !error && (
        <>
          <p role="status" className={s.flowCount}>
            {filtered.length
              ? `${filtered.length} cartões encontrados`
              : rows.length
                ? "Nenhum cartão encontrado. Tente outro cartão ou operadora."
                : "Nenhum cartão disponível no momento."}
          </p>
          {filtered.length > 0 && (
            <ul className={s.instructorList} aria-label="Cartões disponíveis">
              {filtered.map((card) => (
                <li key={card.code}>
                  <button
                    disabled={busy}
                    onClick={() =>
                      onAction({ kind: "card_select", benefit_code: card.code })
                    }
                  >
                    {card.name}
                    <span className={s.cardCode}>
                      {card.uf} · Código {card.code}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <p className={s.flowCount}>
        Você também pode informar o cartão ou mudar de assunto pelo campo de
        mensagem.
      </p>
    </>
  );
}
export function TransportCards({
  state,
  busy,
  onAction,
}: {
  state?: SupportState;
  busy: boolean;
  onAction: (action: SupportAction) => void;
}) {
  if (state?.vt_stage !== "selection" && state?.vt_stage !== "active")
    return null;
  return (
    <section
      className={s.instructorFlow}
      aria-label="Segunda via de vale-transporte"
      aria-busy={busy}
    >
      {state.vt_stage === "selection" ? (
        <CardPicker busy={busy} onAction={onAction} />
      ) : (
        <button
          disabled={busy}
          onClick={() => onAction({ kind: "card_change" })}
        >
          Trocar cartão de transporte
        </button>
      )}
    </section>
  );
}
