import { useId, useState } from "react";
import type { SupportTopic } from "../api/client";
import s from "./Chat.module.css";
export function SupportMenu({
  topics,
  topicId,
  hasMessages,
  busy,
  onTopic,
  onQuestion,
}: {
  topics: SupportTopic[];
  topicId?: string | null;
  hasMessages: boolean;
  busy: boolean;
  onTopic: (id: string | null) => void;
  onQuestion: (topicId: string, questionId: string, text: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  const selected = topics.find((topic) => topic.topic_id === topicId);
  const menu = (
    <div className={`${s.supportMenu} ${selected ? s.selectedSupport : ""}`}>
      <div className={s.fullSupport}>
        {selected ? (
          <>
            <button
              type="button"
              className={s.backTopics}
              disabled={busy}
              onClick={() => onTopic(null)}
            >
              ← Voltar aos assuntos
            </button>
            <h2>{selected.title}</h2>
            {selected.topic_id === "outros" && (
              <p className={s.menuDescription}>
                Escreva sua dúvida no campo de mensagem.
              </p>
            )}
            <div className={s.questionList}>
              {selected.questions
                .filter((q) => q.enabled)
                .map((question) => (
                  <button
                    type="button"
                    disabled={busy}
                    key={question.question_id}
                    onClick={() => {
                      setExpanded(false);
                      onQuestion(
                        selected.topic_id,
                        question.question_id,
                        question.text,
                      );
                    }}
                  >
                    <span>{question.text}</span>
                    <span aria-hidden="true">↗</span>
                  </button>
                ))}
            </div>
          </>
        ) : (
          <div className={s.topicList} aria-label="Assuntos disponíveis">
            {topics
              .filter((t) => t.enabled)
              .map((topic, index) => (
                <button
                  type="button"
                  key={topic.topic_id}
                  disabled={busy}
                  onClick={() => onTopic(topic.topic_id)}
                >
                  <span className={s.number}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span>{topic.title}</span>
                  <span aria-hidden="true">↗</span>
                </button>
              ))}
          </div>
        )}
        {!topics.length && (
          <p role="status" className={s.menuDescription}>
            {busy
              ? "Carregando os assuntos…"
              : "Não foi possível carregar os assuntos. Você pode escrever sua dúvida."}
          </p>
        )}
      </div>
      {topics.length > 0 && (
        <div className={s.compactSupport}>
          {(!selected ||
            !selected.questions.some((question) => question.enabled)) && (
            <>
              <label className="srOnly" htmlFor={`${id}-topic`}>
                Assunto
              </label>
              <select
                id={`${id}-topic`}
                aria-label="Escolher assunto"
                value={topicId ?? ""}
                disabled={busy}
                onChange={(event) => onTopic(event.target.value || null)}
              >
                <option value="">
                  {selected ? "← Voltar aos assuntos" : "Escolha um assunto"}
                </option>
                {topics
                  .filter((topic) => topic.enabled)
                  .map((topic) => (
                    <option key={topic.topic_id} value={topic.topic_id}>
                      {topic.title}
                    </option>
                  ))}
              </select>
            </>
          )}
          {selected && (
            <>
              {selected.questions.some((question) => question.enabled) && (
                <>
                  <label className="srOnly" htmlFor={`${id}-question`}>
                    Pergunta
                  </label>
                  <select
                    id={`${id}-question`}
                    aria-label="Escolher pergunta"
                    value=""
                    disabled={busy}
                    onChange={(event) => {
                      if (event.target.value === "__topics") {
                        onTopic(null);
                        return;
                      }
                      const question = selected.questions.find(
                        (item) => item.question_id === event.target.value,
                      );
                      if (question)
                        onQuestion(
                          selected.topic_id,
                          question.question_id,
                          question.text,
                        );
                    }}
                  >
                    <option value="" disabled>
                      {selected.title} · Escolha uma pergunta
                    </option>
                    <option value="__topics">← Voltar aos assuntos</option>
                    {selected.questions
                      .filter((question) => question.enabled)
                      .map((question) => (
                        <option
                          key={question.question_id}
                          value={question.question_id}
                        >
                          {question.text}
                        </option>
                      ))}
                  </select>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
  if (!hasMessages) return menu;
  return (
    <details
      className={s.continueSupport}
      open={expanded}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary>
        Fazer outra pergunta{selected ? ` · ${selected.title}` : ""}
      </summary>
      {menu}
    </details>
  );
}
