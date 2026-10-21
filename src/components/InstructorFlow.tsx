import { useEffect, useId, useState } from "react";
import type { SupportAction, SupportState } from "../types";
import { request } from "../api/client";
import s from "./Chat.module.css";
type Instructor = { id: string; name: string };
const normalize = (value: string) =>
  value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("pt-BR");
type FlowProps = { busy: boolean; onAction: (action: SupportAction) => void };
function InstructorPicker({ busy, onAction }: FlowProps) {
  const [rows, setRows] = useState<Instructor[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const id = useId();
  useEffect(() => {
    const controller = new AbortController();
    request<Instructor[]>("/support/instructors", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setRows(value);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setError(
            "Não foi possível carregar os instrutores. Tente novamente.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);
  const filtered = rows.filter((row) =>
    normalize(row.name).includes(normalize(query)),
  );
  return (
    <>
      <label htmlFor={id}>Buscar instrutor pelo nome</label>
      <input
        id={id}
        type="search"
        value={query}
        disabled={busy}
        onChange={(event) => setQuery(event.target.value)}
        autoComplete="off"
      />
      {loading && <p role="status">Carregando instrutores…</p>}
      {error && (
        <p role="alert">
          {error}{" "}
          <button
            disabled={busy}
            onClick={() => {
              setLoading(true);
              setError("");
              setAttempt((value) => value + 1);
            }}
          >
            Tentar novamente
          </button>
        </p>
      )}
      {!loading && !error && (
        <>
          <p className={s.flowCount} role="status">
            {filtered.length
              ? `${filtered.length} nomes encontrados`
              : rows.length
                ? "Nenhum instrutor encontrado. Tente outro nome."
                : "Nenhum instrutor disponível no momento."}
          </p>
          {filtered.length > 0 && (
            <ul
              className={s.instructorList}
              aria-label="Instrutores disponíveis"
            >
              {filtered.map((row) => (
                <li key={row.id}>
                  <button
                    disabled={busy}
                    onClick={() =>
                      onAction({
                        kind: "instructor_select",
                        instructor_id: row.id,
                      })
                    }
                  >
                    {row.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <div className={s.flowActions}>
        <button
          disabled={busy}
          onClick={() => onAction({ kind: "instructor_unknown" })}
        >
          Não sei quem é.
        </button>
        <button
          disabled={busy}
          onClick={() => onAction({ kind: "instructor_cancel" })}
        >
          Cancelar seleção
        </button>
      </div>
    </>
  );
}
export function InstructorFlow({
  state,
  busy,
  onAction,
}: FlowProps & { state?: SupportState }) {
  if (!state?.asked) return null;
  const send = (kind: SupportAction["kind"]) => onAction({ kind });
  return (
    <section
      className={s.instructorFlow}
      aria-label="Atendimento com instrutor"
      aria-busy={busy}
    >
      {state.stage === "confirmation" && (
        <div className={s.flowActions}>
          <button disabled={busy} onClick={() => send("instructor_known")}>
            Sim, sei quem é.
          </button>
          <button disabled={busy} onClick={() => send("instructor_unknown")}>
            Não sei quem é.
          </button>
          <button disabled={busy} onClick={() => send("instructor_cancel")}>
            Agora não
          </button>
        </div>
      )}
      {state.stage === "selection" && (
        <InstructorPicker busy={busy} onAction={onAction} />
      )}
      {(state.stage === "contact" || state.stage === "idle") && (
        <button disabled={busy} onClick={() => send("instructor_resume")}>
          Voltar à lista de instrutores
        </button>
      )}
    </section>
  );
}
