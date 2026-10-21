import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { clipboardMessageText } from "./messageText";
import s from "./Chat.module.css";

export function CopyResponse({ content }: { content: string }) {
  const [feedback, setFeedback] = useState<"" | "copied" | "error">("");
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
    };
  }, []);
  async function copy() {
    if (inFlight.current) return;
    inFlight.current = true;
    clearTimeout(timer.current);
    setFeedback("");
    setPending(true);
    try {
      if (!navigator.clipboard?.writeText)
        throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(clipboardMessageText(content));
      if (mounted.current) setFeedback("copied");
    } catch {
      if (mounted.current) setFeedback("error");
    } finally {
      inFlight.current = false;
      if (mounted.current) {
        setPending(false);
        timer.current = setTimeout(() => setFeedback(""), 2500);
      }
    }
  }
  return (
    <div className={s.messageActions}>
      <button
        type="button"
        className={s.copyButton}
        aria-label="Copiar resposta"
        title="Copiar resposta"
        aria-busy={pending}
        disabled={pending}
        data-feedback={Boolean(feedback)}
        onClick={() => {
          void copy();
        }}
      >
        <Icon name={feedback === "copied" ? "check" : "copy"} />
      </button>
      <span
        className={feedback === "error" ? s.copyError : s.copyFeedback}
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {feedback === "copied"
          ? "Copiado"
          : feedback === "error"
            ? "Não foi possível copiar"
            : ""}
      </span>
    </div>
  );
}
