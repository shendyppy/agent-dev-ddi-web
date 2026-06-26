/** Chat widget — Preact island.
 *
 * Loaded via `client:load` from index.astro. Streams responses from
 * the FastAPI backend's /api/chat SSE endpoint.
 */
import { useState, useRef, useEffect } from 'preact/hooks';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import './Chat.css';

type Message = { role: 'user' | 'assistant'; content: string };

const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endOfMessagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, busy]);

  const handleInput = (e: Event) => {
    const target = e.target as HTMLTextAreaElement;
    setInput(target.value);
    // Auto-resize textarea
    target.style.height = 'auto';
    target.style.height = `${Math.min(target.scrollHeight, 200)}px`;
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  async function send() {
    if (!input.trim() || busy) return;

    const currentInput = input;
    const next: Message[] = [...messages, { role: 'user', content: currentInput }];
    setMessages(next);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setBusy(true);

    try {
      const res = await fetch(`${API_BASE}/api/portrai-cms-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: currentInput }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      const assistantMessage = data.response || data.error || 'No response';

      setMessages([...next, { role: 'assistant', content: assistantMessage }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `error: ${String(err)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div class="app-container">
      <header class="header">
        <h1>Product Agent</h1>
      </header>

      <div class="chat-container">
        <div class="chat-content">
          {messages.length === 0 ? (
            <div class="welcome-message">
              <h2>Hello, Gaes</h2>
              <p>How can I help you with Product documentation today?</p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} class={`message-wrapper ${m.role}`}>
                <div class={`message ${m.role}`}>
                  {m.role === 'assistant' && (
                    <div class="avatar">
                      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                      </svg>
                    </div>
                  )}
                  {m.role === 'assistant' ? (
                    <div
                      class="message-content markdown-body"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(marked.parse(m.content) as string) }}
                    />
                  ) : (
                    <div class="message-content">
                      {m.content}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {busy && (
            <div class="message-wrapper assistant">
              <div class="message assistant">
                <div class="avatar">
                  <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                  </svg>
                </div>
                <div class="message-content">
                  <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={endOfMessagesRef} />
        </div>
      </div>

      <div class="input-container">
        <div class="input-box">
          <textarea
            ref={textareaRef}
            class="input-textarea"
            value={input}
            onInput={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask about a product or feature..."
            disabled={busy}
            rows={1}
          />
          <button
            class="send-button"
            onClick={send}
            disabled={busy || !input.trim()}
            title="Send message"
          >
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
