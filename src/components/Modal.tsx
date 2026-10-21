import { useEffect, useRef, useId, type ReactNode } from "react";
import s from "./Shared.module.css";
import { Icon } from "./Icon";
export function Modal({
  title,
  onClose,
  children,
  panel = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  panel?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement;
    dialog.showModal();
    return () => {
      dialog.close();
      if (previous instanceof HTMLElement && previous.isConnected)
        previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`${s.modal} ${panel ? s.panelModal : ""}`}
      aria-labelledby={titleId}
      onCancel={onClose}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const controls = Array.from(
          event.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), [tabindex]:not([tabindex="-1"])',
          ),
        ).filter((element) => element.getClientRects().length > 0);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className={panel ? "srOnly" : s.modalHeader}>
        <h2 id={titleId}>{title}</h2>
        {!panel && (
          <button
            type="button"
            className={s.iconButton}
            aria-label="Fechar diálogo"
            onClick={onClose}
          >
            <Icon name="close" />
          </button>
        )}
      </div>
      {children}
    </dialog>
  );
}
