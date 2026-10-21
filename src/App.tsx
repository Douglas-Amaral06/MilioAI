import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { offline } from "./api/client";
import { useWorkspace } from "./hooks/useWorkspace";
import type { Conversation } from "./types";
import { Sidebar } from "./components/Sidebar";
import { Chat } from "./components/Chat";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { SignIn } from "./components/SignIn";
import { Modal } from "./components/Modal";
import s from "./App.module.css";
import shared from "./components/Shared.module.css";
type Editing = { kind: "rename" | "delete"; conversation: Conversation } | null;
const DemoControls =
  import.meta.env.DEV && typeof __LOCAL_DEMO__ !== "undefined" && __LOCAL_DEMO__
    ? lazy(() => import("./offline/Controls"))
    : null;
export function App() {
  const {
    state,
    dispatch,
    active,
    storageError,
    needsLogin,
    busy,
    uploading,
    topics,
    selectTopic,
    sendGuided,
    sendSupportAction,
    selectingTopic,
    attachments,
    upload,
    removeAttachment,
    cancelProcessing,
    sendPhase,
  } = useWorkspace();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobilePanel, setMobilePanel] = useState<"nav" | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [title, setTitle] = useState("");
  const [feedback, setFeedback] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const navButton = useRef<HTMLButtonElement>(null);
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 1000px)").matches,
  );
  const notify = (text: string) => setFeedback(text);
  useEffect(() => {
    if (!feedback) return;
    const timer = setTimeout(() => setFeedback(""), 4000);
    return () => clearTimeout(timer);
  }, [feedback]);
  useEffect(() => {
    const media = window.matchMedia("(min-width: 1001px)");
    const close = () => {
      setCompact(!media.matches);
      setMobilePanel(null);
    };
    media.addEventListener("change", close);
    return () => media.removeEventListener("change", close);
  }, []);
  useEffect(() => {
    const viewport = window.visualViewport;
    const resize = () => {
      document.documentElement.style.setProperty(
        "--app-height",
        `${viewport?.height ?? window.innerHeight}px`,
      );
    };
    resize();
    viewport?.addEventListener("resize", resize);
    window.addEventListener("resize", resize);
    return () => {
      viewport?.removeEventListener("resize", resize);
      window.removeEventListener("resize", resize);
      document.documentElement.style.removeProperty("--app-height");
    };
  }, []);
  function closePanel() {
    const target = navButton;
    setMobilePanel(null);
    requestAnimationFrame(() => target.current?.focus());
  }
  function send() {
    if (!(active?.draft ?? state.draft).trim()) return;
    dispatch({
      type: "send",
      id: crypto.randomUUID(),
      messageId: crypto.randomUUID(),
      now: new Date().toISOString(),
    });

    inputRef.current?.focus();
  }
  async function create() {
    const success = await dispatch({
      type: "create",
      id: crypto.randomUUID(),
      now: new Date().toISOString(),
    });
    setMobilePanel(null);
    if (success) notify("Nova conversa criada.");
    requestAnimationFrame(() => inputRef.current?.focus());
  }
  function select(id: string) {
    dispatch({ type: "select", id });
    setMobilePanel(null);
    requestAnimationFrame(() => inputRef.current?.focus());
  }
  const sidebar = (
    <Sidebar
      busy={busy || uploading || selectingTopic}
      conversations={state.conversations}
      activeId={state.activeId}
      onCreate={create}
      onSelect={select}
      onRename={(c) => {
        setTitle(c.title);
        setEditing({ kind: "rename", conversation: c });
      }}
      onDelete={(c) => setEditing({ kind: "delete", conversation: c })}
      onClose={() => {
        setSidebarOpen(false);
        setMobilePanel(null);
        requestAnimationFrame(() => navButton.current?.focus());
      }}
    />
  );
  return (
    <div className={s.app}>
      <a className={s.skip} href="#message">
        Ir para escrever mensagem
      </a>
      {sidebarOpen && (
        <div className={s.desktopNav} id="navigation-panel">
          {sidebar}
        </div>
      )}
      <main className={s.main}>
        <header className={s.header}>
          <div className={s.headerStart}>
            <button
              ref={navButton}
              className={`${shared.iconButton} ${sidebarOpen ? s.mobileMenu : ""}`}
              aria-label="Abrir navegação"
              aria-expanded={mobilePanel === "nav" || (sidebarOpen && !compact)}
              aria-controls={
                compact ? "navigation-panel-mobile" : "navigation-panel"
              }
              onClick={() =>
                compact ? setMobilePanel("nav") : setSidebarOpen(true)
              }
            >
              <Icon name="panel" />
            </button>
            <div className={s.conversationTitle}>
              <span className={s.headerLabel}>ESPAÇO DE TRABALHO</span>
              <span title={active?.title}>
                {active?.title ?? "Nova conversa"}
              </span>
            </div>
          </div>
        </header>
        {DemoControls && (
          <Suspense fallback={null}>
            <DemoControls busy={busy} onCancel={cancelProcessing} />
          </Suspense>
        )}
        {storageError && (
          <div className={s.error} role="alert">
            {storageError}
          </div>
        )}
        <Chat
          conversation={active}
          onSupportAction={(action) => {
            void sendSupportAction(action);
          }}
          attachments={attachments}
          topics={topics}
          busy={busy || uploading || selectingTopic}
          onTopic={(id) => {
            void selectTopic(id).then(() => {
              if (id === "outros") inputRef.current?.focus();
            });
          }}
          onQuestion={(topicId, questionId, text) => {
            void sendGuided(topicId, questionId, text);
          }}
        />
        <Composer
          sendPhase={sendPhase}
          uploadUnavailable={offline}
          draft={active?.draft ?? state.draft}
          onChange={(value) => dispatch({ type: "draft", value })}
          onSend={send}
          inputRef={inputRef}
          busy={busy || selectingTopic}
          uploading={uploading}
          attachments={attachments.filter((file) => !file.message_id)}
          onUpload={upload}
          onRemove={removeAttachment}
        />
      </main>
      {needsLogin && (
        <Modal title="Acessar MilioAI" onClose={() => {}}>
          <SignIn />
        </Modal>
      )}
      {mobilePanel && (
        <Modal panel title="Conversas" onClose={closePanel}>
          <div className={s.mobilePanel} id="navigation-panel-mobile">
            {sidebar}
          </div>
        </Modal>
      )}
      {editing && (
        <Modal
          title={
            editing.kind === "rename"
              ? "Renomear conversa"
              : "Excluir conversa?"
          }
          onClose={() => setEditing(null)}
        >
          {editing.kind === "rename" ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                if (title.trim()) {
                  const success = await dispatch({
                    type: "rename",
                    id: editing.conversation.id,
                    title,
                  });
                  if (success) {
                    setEditing(null);
                    notify("Conversa renomeada.");
                  }
                }
              }}
            >
              <label className={shared.field}>
                Título da conversa
                <input
                  autoFocus
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                  required
                />
              </label>
              <div className={shared.actions}>
                <button
                  type="button"
                  className={shared.button}
                  onClick={() => setEditing(null)}
                >
                  Cancelar
                </button>
                <button
                  className={`${shared.button} ${shared.primary}`}
                  disabled={!title.trim()}
                >
                  Salvar título
                </button>
              </div>
            </form>
          ) : (
            <>
              <p>
                A conversa “{editing.conversation.title}” e suas mensagens serão
                removidas permanentemente. Esta ação não pode ser desfeita.
              </p>
              <div className={shared.actions}>
                <button
                  autoFocus
                  className={shared.button}
                  onClick={() => setEditing(null)}
                >
                  Cancelar
                </button>
                <button
                  className={`${shared.button} ${shared.danger}`}
                  onClick={async () => {
                    const success = await dispatch({
                      type: "delete",
                      id: editing.conversation.id,
                    });
                    if (success) {
                      setEditing(null);
                      notify("Conversa excluída.");
                    }
                    requestAnimationFrame(() => inputRef.current?.focus());
                  }}
                >
                  Excluir conversa
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className={feedback ? s.toast : "srOnly"}
      >
        {feedback}
      </div>
    </div>
  );
}
