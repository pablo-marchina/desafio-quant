import { useState } from "react";

function renderMessageBody(text) {
  const blocks = String(text || "")
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter(Boolean);

  return blocks.map((block, blockIndex) => {
    const lines = block
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    const isBulletList = lines.length > 1 && lines.every((line) => /^[-*•]\s+/.test(line));
    if (isBulletList) {
      return (
        <ul key={`block-${blockIndex}`} className="chat-list">
          {lines.map((line, lineIndex) => (
            <li key={`item-${blockIndex}-${lineIndex}`}>{line.replace(/^[-*•]\s+/, "")}</li>
          ))}
        </ul>
      );
    }

    const isNumberedList = lines.length > 1 && lines.every((line) => /^\d+\.\s+/.test(line));
    if (isNumberedList) {
      return (
        <ol key={`block-${blockIndex}`} className="chat-list numbered">
          {lines.map((line, lineIndex) => (
            <li key={`item-${blockIndex}-${lineIndex}`}>{line.replace(/^\d+\.\s+/, "")}</li>
          ))}
        </ol>
      );
    }

    if (lines.length === 1 && /:\s*$/.test(lines[0])) {
      return (
        <h4 key={`block-${blockIndex}`} className="chat-subtitle">
          {lines[0]}
        </h4>
      );
    }

    return (
      <p key={`block-${blockIndex}`} className="chat-paragraph">
        {lines.join(" ")}
      </p>
    );
  });
}

function renderSources(sources = []) {
  if (!Array.isArray(sources) || sources.length === 0) {
    return null;
  }

  return (
    <div className="chat-sources">
      <span>Fontes</span>
      <ul className="chat-source-list">
        {sources.map((source, index) => (
          <li key={`${source.url || source.title || "source"}-${index}`}>
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.title || source.citation || source.url}
              </a>
            ) : (
              source.title || source.citation || "Fonte relacionada"
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ChatPanel({ messages, onSendMessage, isSending = false, disabled = false }) {
  const [input, setInput] = useState("");

  const submitMessage = () => {
    if (disabled || isSending) return;
    onSendMessage(input);
    setInput("");
  };

  return (
    <section className="panel chat-panel">
      <div className="section-heading">
        <div>
          <p className="section-label">Chat de consulta</p>
          <h2>Radar assistente</h2>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="empty-state">
            {disabled
              ? "Selecione ou analise uma startup para habilitar o chat com LLM."
              : "Nenhuma mensagem ainda. Use o campo abaixo para iniciar uma consulta."}
          </div>
        ) : null}
        {messages.map((message) => (
          <article key={message.id} className={`chat-bubble ${message.role}`}>
            <span>{message.role === "assistant" ? "Radar" : "Voce"}</span>
            <div className="chat-body">{renderMessageBody(message.text)}</div>
            {message.role === "assistant" ? renderSources(message.sources) : null}
          </article>
        ))}
      </div>

      <div className="chat-input">
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Pergunte sobre fit NVIDIA, sinais de IA ou recomendacoes..."
          rows={3}
          disabled={disabled || isSending}
        />
        <button className="button primary" type="button" onClick={submitMessage} disabled={disabled || isSending}>
          {isSending ? "Consultando..." : "Enviar"}
        </button>
      </div>
    </section>
  );
}
