// V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
// Miguel. Do not extend without a rebuild pass. See build spec Definition
// of Done.
//
// Text chat only. Uses the browser's native EventSource against the
// backend's GET+SSE endpoints (see valka_agent/api/main.py for why GET
// instead of POST). Escalation is surfaced as a highlighted banner plus a
// separate "reply as team member" input that calls /api/resume — a real
// human-in-the-loop control, not just a visible-but-inert indicator.
import { useEffect, useRef, useState } from "react";

// VITE_API_BASE is baked in at build time (Vite only exposes env vars
// prefixed VITE_ to client code). Render's static site build sets this to
// the deployed backend's URL; falls back to localhost for local dev.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function getThreadId() {
  const key = "valka-thread-id";
  let id = localStorage.getItem(key);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
}

export default function App() {
  const [threadId] = useState(getThreadId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [humanReply, setHumanReply] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [escalation, setEscalation] = useState(null); // { reason, conversation_tail } | null
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, escalation]);

  function appendMessage(msg) {
    setMessages((prev) => [...prev, msg]);
  }

  function appendToLastAssistant(text) {
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = {
        ...next[next.length - 1],
        text: next[next.length - 1].text + text,
      };
      return next;
    });
  }

  function streamFrom(url, { onEscalated } = {}) {
    setStreaming(true);
    appendMessage({ role: "assistant", text: "" });

    const es = new EventSource(url);

    es.addEventListener("chunk", (e) => {
      const { text } = JSON.parse(e.data);
      appendToLastAssistant(text);
    });

    es.addEventListener("escalated", (e) => {
      const payload = JSON.parse(e.data);
      // Drop the empty assistant placeholder — the graph paused before
      // producing a reply, so there's nothing to show in that bubble.
      setMessages((prev) => prev.slice(0, -1));
      setEscalation(payload);
      onEscalated?.(payload);
    });

    es.addEventListener("state", () => {
      // Room for surfacing intent/kb_citations in the UI later; not needed
      // for the demo script itself.
    });

    es.addEventListener("done", () => {
      es.close();
      setStreaming(false);
    });

    es.onerror = () => {
      es.close();
      setStreaming(false);
      appendToLastAssistant("\n\n[connection error — is the API running on :8000?]");
    };
  }

  function sendMessage(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || streaming) return;
    appendMessage({ role: "user", text });
    setInput("");
    const url = `${API_BASE}/api/chat?thread_id=${encodeURIComponent(threadId)}&message=${encodeURIComponent(text)}`;
    streamFrom(url);
  }

  function sendHumanReply(e) {
    e.preventDefault();
    const text = humanReply.trim();
    if (!text || streaming) return;
    setEscalation(null);
    setHumanReply("");
    const url = `${API_BASE}/api/resume?thread_id=${encodeURIComponent(threadId)}&reply=${encodeURIComponent(text)}`;
    streamFrom(url);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Valka Agent</h1>
        <span className="v1-badge">v1 demo</span>
      </header>

      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={`bubble bubble-${m.role}`}>
            {m.text || (streaming && i === messages.length - 1 ? "…" : "")}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {escalation && (
        <div className="escalation-banner">
          <strong>Escalated — waiting for a team member.</strong>
          <div className="escalation-reason">{escalation.reason}</div>
          <form onSubmit={sendHumanReply} className="escalation-form">
            <input
              value={humanReply}
              onChange={(e) => setHumanReply(e.target.value)}
              placeholder="Reply as the team member to resume the conversation..."
              disabled={streaming}
            />
            <button type="submit" disabled={streaming || !humanReply.trim()}>
              Send &amp; resume
            </button>
          </form>
        </div>
      )}

      <form onSubmit={sendMessage} className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={escalation ? "Waiting on a team member's reply above..." : "Type a message..."}
          disabled={streaming || Boolean(escalation)}
        />
        <button type="submit" disabled={streaming || Boolean(escalation) || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
