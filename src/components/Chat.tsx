import { useConversationScroll } from "../hooks/useConversationScroll";
import { CopyResponse } from "./CopyResponse";
import { visibleMessageText } from "./messageText";
import { Icon } from "./Icon";
import type { Conversation, SupportAction } from "../types";
import s from "./Chat.module.css";
import { TransportCards } from "./TransportCards";
import { InstructorFlow } from "./InstructorFlow";
import { AssistantResponse } from "./AssistantResponse";
import { SupportMenu } from "./SupportMenu";
import type { SupportTopic, Attachment } from "../api/client";
export function Chat({
  conversation,
  topics,
  onTopic,
  onQuestion,
  busy,
  attachments,
  onSupportAction,
}: {
  conversation?: Conversation;
  onSupportAction?: (action: SupportAction) => void;
  attachments: Attachment[];
  topics: SupportTopic[];
  busy: boolean;
  onTopic: (id: string | null) => void;
  onQuestion: (topicId: string, questionId: string, text: string) => void;
}) {
  const { region, content, onScroll, goToLatest, showLatest } =
    useConversationScroll(conversation);
  return (
    <div className={s.history}>
      <div
        ref={region}
        onScroll={onScroll}
        className={`${s.content} ${conversation?.messages.length ? "" : s.homeContent}`}
        role="region"
        tabIndex={0}
        aria-label="Conteúdo da conversa"
      >
        {!conversation?.messages.length ? (
          <section
            ref={content}
            className={s.welcome}
            aria-labelledby="welcome-title"
          >
            <div className={s.welcomeTop}>
              <span className={s.eyebrow}>MILIOAI / ESPAÇO DE CONVERSA</span>
              <div className={s.art} aria-hidden="true">
                <i />
                <i />
                <i />
              </div>
            </div>
            <div className={s.intro}>
              <span className={s.hello}>Olá.</span>
              <h1 id="welcome-title">
                Como posso <br />
                ajudar?
              </h1>
            </div>
            <SupportMenu
              topics={topics}
              topicId={conversation?.topicId}
              hasMessages={false}
              busy={busy}
              onTopic={onTopic}
              onQuestion={onQuestion}
            />
          </section>
        ) : (
          <section
            ref={content}
            className={s.messages}
            aria-label="Mensagens enviadas"
          >
            <div className={s.conversationStart}>
              <span>CONVERSA</span>
              <span>
                {new Date(conversation.createdAt).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "long",
                })}
              </span>
            </div>
            {conversation.messages.map((m) => (
              <article
                key={m.id}
                className={`${s.message} ${m.role === "user" ? s.userMessage : s.assistantMessage}`}
                aria-label={
                  m.role === "user" ? "Mensagem de você" : "Resposta do MilioAI"
                }
                aria-busy={m.status === "processing"}
              >
                <header>
                  <strong
                    className={m.role === "user" ? "srOnly" : s.signature}
                  >
                    {m.role === "user" ? "Você" : "MilioAI"}
                  </strong>
                  <time dateTime={m.createdAt}>
                    {new Date(m.createdAt).toLocaleTimeString("pt-BR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </time>
                </header>
                {m.status === "processing" && (
                  <span className={s.processing} role="status">
                    {m.content
                      ? "Respondendo…"
                      : "MilioAI está preparando a resposta…"}
                  </span>
                )}
                <div className={s.messageBody}>
                  {m.role === "user" ? (
                    <p>{m.content}</p>
                  ) : (
                    <>
                      <AssistantResponse
                        content={visibleMessageText(m.content)}
                        contacts={m.contacts}
                      />
                    </>
                  )}
                </div>
                {(m.status === "failed" || m.status === "cancelled") && (
                  <p
                    className={
                      m.status === "failed" ? s.messageError : s.processing
                    }
                  >
                    {m.status === "cancelled"
                      ? "A resposta foi interrompida."
                      : "Não foi possível concluir esta resposta."}{" "}
                    Você pode enviar uma nova mensagem.
                  </p>
                )}
                {m.role === "assistant" &&
                  m.sources &&
                  m.sources.length > 0 && (
                    <details className={s.references}>
                      <summary>Fontes consultadas ({m.sources.length})</summary>
                      {m.sources.map((source) => (
                        <div key={source.id}>
                          <strong>{source.title}</strong>
                          <p>
                            {source.section && <span>{source.section} · </span>}
                            Versão {source.version}
                            {source.page
                              ? ` · Página ${source.page}`
                              : ` · Trecho ${(source.chunk ?? 0) + 1}`}
                            {source.is_test
                              ? " · Material fictício de teste"
                              : ""}
                          </p>
                          {source.validation_only && (
                            <p>
                              Documento fornecido para validação local; vigência
                              ainda não confirmada.
                            </p>
                          )}
                          <blockquote>{source.excerpt}</blockquote>
                        </div>
                      ))}
                    </details>
                  )}
                {attachments
                  .filter((file) => file.message_id === m.id)
                  .map((file) => (
                    <p className={s.processing} key={file.id}>
                      Anexo: {file.name} · Armazenado, sem interpretação pela IA
                    </p>
                  ))}
                {m.role === "assistant" &&
                  m.status !== "processing" &&
                  visibleMessageText(m.content).trim() && (
                    <CopyResponse content={m.content} />
                  )}
              </article>
            ))}
            {onSupportAction && (
              <TransportCards
                key={`vt-${conversation.id}`}
                state={conversation.supportState}
                busy={busy}
                onAction={onSupportAction}
              />
            )}
            {onSupportAction &&
              !["selection", "active"].includes(
                conversation.supportState?.vt_stage ?? "",
              ) && (
                <InstructorFlow
                  key={conversation.id}
                  state={conversation.supportState}
                  busy={busy}
                  onAction={onSupportAction}
                />
              )}
            <SupportMenu
              topics={topics}
              topicId={conversation?.topicId}
              hasMessages
              busy={busy}
              onTopic={onTopic}
              onQuestion={onQuestion}
            />
          </section>
        )}
      </div>
      {showLatest && (
        <div className={s.latestAction}>
          <button
            type="button"
            onClick={goToLatest}
            className={s.latestButton}
            aria-label="Ir para a última mensagem"
            title="Ir para a última mensagem"
          >
            <Icon name="down" />
          </button>
        </div>
      )}
    </div>
  );
}
