/** Chat widget — Preact island.
 *
 * Loaded via `client:load` from index.astro. Streams responses from
 * the FastAPI backend's /api/chat SSE endpoint.
 */
import { useState } from 'preact/hooks';

type Message = { role: 'user' | 'assistant'; content: string };

const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);

  async function send(e: Event) {
    e.preventDefault();
    if (!input.trim() || busy) return;

    const next: Message[] = [...messages, { role: 'user', content: input }];
    setMessages(next);
    setInput('');
    setBusy(true);

    try {
      const res = await fetch(`${API_BASE}/api/portrai-cms-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input }),
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
    <div style="max-width:760px;margin:2rem auto;font-family:system-ui,sans-serif">
      <div style="border:1px solid #ddd;border-radius:8px;padding:1rem;min-height:400px;background:#fafafa">
        {messages.length === 0 && (
          <p style="color:#888">
            Ask about a product, a feature, how to run an app, or request a
            screenshot.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} style="margin-bottom:0.75rem">
            <strong>{m.role === 'user' ? 'You' : 'Agent'}:</strong>{' '}
            <span style="white-space:pre-wrap">{m.content}</span>
          </div>
        ))}
      </div>
      <form onSubmit={send} style="display:flex;gap:0.5rem;margin-top:0.75rem">
        <input
          type="text"
          value={input}
          onInput={(e) => setInput((e.target as HTMLInputElement).value)}
          placeholder="How do I run product X?"
          style="flex:1;padding:0.5rem;border:1px solid #ccc;border-radius:6px"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy}
          style="padding:0.5rem 1rem;border-radius:6px;border:0;background:#111;color:#fff;cursor:pointer"
        >
          {busy ? '…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
