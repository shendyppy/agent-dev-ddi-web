/**
 * The slug preview must agree with the server, character for character.
 *
 * It is shown to the user as "Disimpan sebagai <name>", and the publish
 * endpoint addresses documents by that same name. A preview that drifts from
 * `server._safe_doc_name` would be a confident lie about where the document
 * went — so these cases are copied from the backend's own tests on purpose.
 */

import { describe, expect, it } from 'vitest';
import { previewSlug } from './KnowledgeBaseModal';

describe('previewSlug', () => {
  it('slugifies an ordinary title', () => {
    expect(previewSlug('Fitur Login')).toBe('fitur-login.md');
  });

  it('does not turn an existing .md suffix into -md', () => {
    // The bug this locks: the dot was replaced before the suffix check, so
    // "fitur-login.md" became "fitur-login-md.md" and publish could not find it.
    expect(previewSlug('fitur-login.md')).toBe('fitur-login.md');
  });

  it('collapses punctuation the same way the server does', () => {
    expect(previewSlug('FAQ')).toBe('faq.md');
    expect(previewSlug('faq!!!')).toBe('faq.md');
  });

  it('renders path traversal harmless rather than hiding it', () => {
    expect(previewSlug('../../etc/passwd')).toBe('etc-passwd.md');
  });

  it('falls back to untitled for an empty title', () => {
    expect(previewSlug('')).toBe('untitled.md');
    expect(previewSlug('!!!')).toBe('untitled.md');
  });
});
