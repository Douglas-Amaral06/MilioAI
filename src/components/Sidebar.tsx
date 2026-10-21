import { useState } from "react";
import type { Conversation } from "../types";
import { authConfigured, logout } from "../api/client";
import { Icon } from "./Icon";
import s from "./Sidebar.module.css";
import shared from "./Shared.module.css";
interface Props {
  busy?: boolean;
  conversations: Conversation[];
  activeId: string | null;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onRename: (c: Conversation) => void;
  onDelete: (c: Conversation) => void;
  onClose: () => void;
}
const normalize = (text: string) =>
  text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("pt-BR");
export function Sidebar({
  busy = false,
  conversations,
  activeId,
  onCreate,
  onSelect,
  onRename,
  onDelete,
  onClose,
}: Props) {
  const [query, setQuery] = useState("");
  const results = conversations.filter((c) =>
    normalize(c.title).includes(normalize(query)),
  );
  const today = new Date().toLocaleDateString("pt-BR");
  const groups = [
    {
      title: "Hoje",
      items: results.filter(
        (c) => new Date(c.updatedAt).toLocaleDateString("pt-BR") === today,
      ),
    },
    {
      title: "Anteriores",
      items: results.filter(
        (c) => new Date(c.updatedAt).toLocaleDateString("pt-BR") !== today,
      ),
    },
  ];
  return (
    <nav className={s.sidebar} aria-label="Conversas">
      <div className={s.identity}>
        <span className={s.wordmark}>
          Milio<span>AI</span>
          <i aria-hidden="true" />
        </span>
        <button
          className={shared.iconButton}
          onClick={onClose}
          aria-label="Recolher navegação"
        >
          <Icon name="panel" />
        </button>
      </div>
      <p className={s.subline}>Seu espaço de orientação</p>
      <button className={s.newConversation} disabled={busy} onClick={onCreate}>
        <Icon name="plus" />
        Nova conversa<span aria-hidden="true">↗</span>
      </button>
      <label className={s.search}>
        <Icon name="search" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar conversas"
          aria-label="Buscar conversas pelo título"
        />
      </label>
      <div className={s.history}>
        <div className={s.historyHeading}>
          <h2>Suas conversas</h2>
          <span>{conversations.length.toString().padStart(2, "0")}</span>
        </div>
        {results.length === 0 ? (
          <div className={s.empty}>
            <span className={s.emptyLine} aria-hidden="true" />
            <p role="status">
              {query
                ? "Nenhuma conversa encontrada."
                : "Tudo começa com uma pergunta."}
            </p>
            <small>
              {query
                ? "Experimente buscar outro título."
                : "Suas conversas aparecerão aqui."}
            </small>
          </div>
        ) : (
          groups.map(
            (group) =>
              group.items.length > 0 && (
                <section key={group.title} className={s.group}>
                  <h3>{group.title}</h3>
                  <ul>
                    {group.items.map((c) => (
                      <li
                        key={c.id}
                        className={c.id === activeId ? s.selected : undefined}
                      >
                        <button
                          className={s.conversation}
                          disabled={busy}
                          onClick={() => onSelect(c.id)}
                          aria-current={c.id === activeId ? "page" : undefined}
                          title={c.title}
                        >
                          {c.title}
                        </button>
                        <div className={s.itemActions}>
                          <button
                            className={shared.iconButton}
                            onClick={() => onRename(c)}
                            disabled={busy}
                            aria-label={`Renomear ${c.title}`}
                          >
                            <Icon name="edit" />
                          </button>
                          <button
                            className={shared.iconButton}
                            onClick={() => onDelete(c)}
                            disabled={busy}
                            aria-label={`Excluir ${c.title}`}
                          >
                            <Icon name="trash" />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              ),
          )
        )}
      </div>
      <footer className={s.footer}>
        <p>
          Suas conversas são privadas.
          <br />
        </p>
        {authConfigured && (
          <button type="button" className={s.signOut} onClick={logout}>
            Sair
          </button>
        )}
      </footer>
    </nav>
  );
}
