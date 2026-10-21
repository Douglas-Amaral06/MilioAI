import { useLayoutEffect, type RefObject } from "react";
import { Icon } from "./Icon";
import s from "./Chat.module.css";
import { useRef } from "react";
import type { Attachment } from "../api/client";
export function Composer({
  draft,
  onChange,
  onSend,
  inputRef,
  busy,
  uploading,
  attachments,
  onUpload,
  onRemove,
  uploadUnavailable = false,
  sendPhase = "idle",
}: {
  sendPhase?: "idle" | "sending" | "responding";
  uploadUnavailable?: boolean;
  busy: boolean;
  uploading: boolean;
  attachments: Attachment[];
  onUpload: (file: File) => void;
  onRemove: (id: string) => void;
  draft: string;
  onChange: (value: string) => void;
  onSend: () => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  useLayoutEffect(() => {
    const field = inputRef.current;
    if (field) {
      field.style.height = "auto";
      field.style.height = `${field.scrollHeight}px`;
    }
  }, [draft, inputRef]);
  return (
    <div className={s.composerArea}>
      {attachments.length > 0 && (
        <ul className={s.pendingFiles}>
          {attachments.map((file) => (
            <li key={file.id}>
              <span>{file.name}</span>
              <button
                type="button"
                disabled={busy || uploading}
                onClick={() => onRemove(file.id)}
                aria-label={`Remover ${file.name}`}
              >
                <Icon name="close" />
              </button>
            </li>
          ))}
        </ul>
      )}
      {uploading && (
        <p className={s.storageNote} role="status">
          Enviando arquivo…
        </p>
      )}
      <input
        className="srOnly"
        type="file"
        ref={fileInput}
        tabIndex={-1}
        aria-label="Selecionar anexo"
        accept=".pdf,.txt,.md"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onUpload(file);
          event.target.value = "";
        }}
      />
      <form
        className={s.composer}
        onSubmit={(e) => {
          e.preventDefault();
          if (!busy && !uploading && draft.trim()) onSend();
        }}
      >
        <label className="srOnly" htmlFor="message">
          Sua mensagem
        </label>
        <button
          type="button"
          className={s.attachButton}
          disabled={
            uploadUnavailable || busy || uploading || attachments.length >= 5
          }
          title={
            uploadUnavailable
              ? "Upload real indisponível na demonstração local"
              : undefined
          }
          onClick={() => fileInput.current?.click()}
          aria-label="Anexar arquivos"
        >
          <Icon name="plus" />
        </button>
        <textarea
          ref={inputRef}
          id="message"
          rows={1}
          value={draft}
          disabled={busy || uploading}
          maxLength={4000}
          placeholder="Escreva sua pergunta…"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              if (!busy && !uploading && draft.trim()) onSend();
            }
          }}
        />
        <button
          className={s.sendButton}
          type="submit"
          disabled={!draft.trim() || busy || uploading}
          aria-label={
            sendPhase === "sending"
              ? "Enviando mensagem"
              : sendPhase === "responding"
                ? "Aguardando resposta"
                : "Enviar mensagem"
          }
        >
          <Icon name={sendPhase === "idle" ? "arrow" : "pending"} />
        </button>
      </form>
      <div className={s.composerNote}>
        <span role="status" aria-live="polite" aria-atomic="true">
          {sendPhase === "sending" ? (
            "Enviando mensagem…"
          ) : sendPhase === "responding" ? (
            "Resposta em andamento."
          ) : (
            <>
              Enter envia <b aria-hidden="true">·</b> Shift + Enter quebra a
              linha
            </>
          )}
        </span>
      </div>
      <p className={s.storageNote}>
        {uploadUnavailable
          ? "Upload real indisponível na demonstração local. Nenhum arquivo é enviado ou armazenado."
          : "Anexos ficam nesta conversa e não são interpretados pela IA."}
      </p>
    </div>
  );
}
