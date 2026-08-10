import { describe, expect, it } from 'vitest';
import { mapErrorToFriendly, parseSSE, renderMarkdown } from './chat';
import { COPY } from './copy';

const copy = COPY.en;

/** A ReadableStream of UTF-8 bytes, matching what `fetch` hands back as `res.body`. */
function bodyOf(...frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame));
      controller.close();
    },
  });
}

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of parseSSE(stream)) events.push(event);
  return events;
}

describe('mapErrorToFriendly', () => {
  it('puts the daily-quota check ahead of the generic 429 branch', () => {
    // Both strings contain "quota"; only the per-day one may reach
    // errorQuotaExhausted, because "wait a moment and retry" is the one piece
    // of advice guaranteed not to work against a daily cap.
    const daily = 'RateLimitError: 429 quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier';
    expect(mapErrorToFriendly(daily, copy)).toBe(copy.errorQuotaExhausted);
    expect(mapErrorToFriendly('429 quota exceeded', copy)).toBe(copy.errorRateLimit);
  });

  it('gives the loop guard its own copy', () => {
    expect(mapErrorToFriendly('GraphRecursionError: limit of 25 reached', copy)).toBe(
      copy.errorLoopGuard,
    );
  });

  it('maps upstream unavailability', () => {
    expect(mapErrorToFriendly('APIError: 503 Service Unavailable', copy)).toBe(
      copy.errorServiceUnavailable,
    );
  });

  it('falls back to the generic message rather than leaking a stack trace', () => {
    expect(mapErrorToFriendly('KeyError: "session_id"', copy)).toBe(copy.errorGeneric);
  });
});

describe('parseSSE', () => {
  it('parses CRLF-separated frames', async () => {
    // sse-starlette 3.x emits CRLF. Splitting on "\n\n" only would drop every
    // frame, which is the bug that once surfaced as a phantom dropped connection.
    const events = await collect(
      bodyOf(
        'event: message\r\ndata: {"role":"assistant"}\r\n\r\n',
        'event: done\r\ndata: {}\r\n\r\n',
      ),
    );
    expect(events.map((e) => e.event)).toEqual(['message', 'done']);
  });

  it('parses LF-separated frames', async () => {
    const events = await collect(bodyOf('event: message\ndata: {"role":"assistant"}\n\n'));
    expect(events.map((e) => e.event)).toEqual(['message']);
  });

  it('reassembles a frame split across chunk boundaries', async () => {
    const events = await collect(bodyOf('event: mess', 'age\ndata: {"a":1}\n', '\n'));
    expect(events).toHaveLength(1);
    expect(events[0].event).toBe('message');
  });
});

describe('renderMarkdown', () => {
  it('forces target and rel on links so an LLM-emitted URL cannot tab-nap', () => {
    const html = renderMarkdown('[click](https://example.com)');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it('strips script tags out of model output', () => {
    const html = renderMarkdown('<script>alert(1)</script>hello');
    expect(html).not.toContain('<script>');
    expect(html).toContain('hello');
  });

  it('renders GFM tables even with Windows (CRLF) line endings', () => {
    // Offline answers quote docs indexed on Windows, so chunk text can carry
    // \r\n. marked v18 parses headings fine with CRLF but drops tables to
    // per-row <p>| … |</p> paragraphs — the raw-pipe soup bug.
    const table = '| A | B |\r\n|---|---|\r\n| 1 | 2 |\r\n';
    const html = renderMarkdown(table);
    expect(html).toContain('<table>');
    expect(html).not.toContain('| A | B |');
  });
});
