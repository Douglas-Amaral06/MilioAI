import { useState } from "react";
import { resetDemo, setScenario } from "./adapter";
import type { Scenario } from "./fixtures";
import s from "./Controls.module.css";
export default function Controls({
  busy,
  onCancel,
}: {
  busy: boolean;
  onCancel: () => void;
}) {
  const [value, setValue] = useState<Scenario>("success");
  return (
    <div className={s.controls} role="region" aria-label="Demonstração local">
      <small>Demonstração local · Visitante fictício</small>{" "}
      <label>
        Cenário de resposta{" "}
        <select
          disabled={busy}
          value={value}
          onChange={(e) => {
            const next = e.target.value as Scenario;
            setValue(next);
            setScenario(next);
          }}
        >
          <option value="success">Resposta curta</option>
          <option value="sources">Com fontes</option>
          <option value="long">Resposta longa</option>
          <option value="empty">Sem informações</option>
          <option value="error">Falha controlada</option>
          <option value="slow">Processamento lento</option>
        </select>
      </label>{" "}
      <button disabled={!busy} onClick={onCancel}>
        Cancelar processamento
      </button>{" "}
      <button
        disabled={busy}
        onClick={() => {
          resetDemo();
          window.location.reload();
        }}
      >
        Limpar demonstração
      </button>
    </div>
  );
}
