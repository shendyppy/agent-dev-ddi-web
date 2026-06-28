/**
 * Bilingual UI copy — the single source of truth for every user-facing string.
 *
 * One flat object per language. The active language is held in component state
 * and persisted to localStorage. Never inline a literal string in JSX — add a
 * key here so both languages stay in lockstep.
 *
 * Voice: write like a real teammate, not a manual. No em-dashes, no jargon, no
 * status codes in user-facing text. Keep Bahasa casual-professional and English
 * plain.
 */

export type Language = 'id' | 'en';

export type Copy = {
  appTitle: string;
  langLabel: string;
  langToggleAria: string;
  // Plain string — no colored accent word (avoids the #1 "generic AI UI" tell).
  welcomeHeading: string;
  welcomeSubtitle: string;
  suggestedPrompts: string[];
  inputPlaceholder: string;
  inputLabel: string;
  sendLabel: string;
  sendAria: string;
  chatLogLabel: string;
  typingThinking: string;
  typingSearching: string;
  toolCalling: string;
  toolResult: (chars: number) => string;
  errorPrefix: string;
  errorHint: string;
  errorStreamDropped: string;
  errorRetry: string;
  // Granular error messages that replace the raw exception string.
  errorRateLimit: string;
  errorServiceUnavailable: string;
  errorGeneric: string;
  productScopeLabel: string;
  productScopeAll: string;
  productScopeAria: string;
};

export const COPY: Record<Language, Copy> = {
  id: {
    appTitle: 'Documentation Agent',
    langLabel: 'Bahasa',
    langToggleAria: 'Ganti bahasa',
    welcomeHeading: 'Ada yang bisa dibantu?',
    welcomeSubtitle:
      'Saya bisa bantu cari dokumentasi, lihat fitur, cara menjalankan produk, sampai ambil screenshot. Tanya pakai Bahasa Indonesia atau English.',
    suggestedPrompts: [
      'Gimana cara menjalankan proyek di lokal?',
      'Fitur apa aja yang tersedia?',
      'Di mana dokumentasi soal autentikasi?',
    ],
    inputPlaceholder: 'Coba: "Gimana cara jalanin X?" atau "Di mana fitur export?"',
    inputLabel: 'Tulis pertanyaan',
    sendLabel: 'Kirim',
    sendAria: 'Kirim pesan (Enter)',
    chatLogLabel: 'Riwayat percakapan',
    typingThinking: 'Lagi mikir…',
    typingSearching: 'Lagi cari di dokumentasi…',
    toolCalling: 'Lagi cari di dokumentasi…',
    toolResult: () => 'Ketemu di dokumentasi',
    errorPrefix: 'Waduh, ada yang nggak beres.',
    errorHint: '',
    errorStreamDropped: 'Koneksinya keputus. Coba lagi, ya?',
    errorRetry: 'Coba lagi',
    errorRateLimit: 'Asisten lagi sibuk banget. Tunggu sebentar, lalu coba lagi.',
    errorServiceUnavailable: 'Layanannya lagi nggak tersedia. Coba lagi beberapa saat lagi, ya.',
    errorGeneric: 'Ada yang nggak beres. Coba kirim lagi pertanyaannya.',
    productScopeLabel: 'Fokus:',
    productScopeAll: 'Semua produk',
    productScopeAria: 'Pilih produk yang ingin difokuskan',
  },
  en: {
    appTitle: 'Documentation Agent',
    langLabel: 'Language',
    langToggleAria: 'Change interface language',
    welcomeHeading: 'What can I help you with?',
    welcomeSubtitle:
      'I can help you find docs, explore features, figure out how to run a product, and grab screenshots. Ask in English or Bahasa.',
    suggestedPrompts: [
      'How do I run the project locally?',
      'What features are available?',
      'Where are the docs on authentication?',
    ],
    inputPlaceholder: 'Try: "How do I run X?" or "Where is the export feature?"',
    inputLabel: 'Type a question',
    sendLabel: 'Send',
    sendAria: 'Send message (Enter)',
    chatLogLabel: 'Conversation log',
    typingThinking: 'Thinking…',
    typingSearching: 'Searching the docs…',
    toolCalling: 'Searching the docs…',
    toolResult: () => 'Found in the docs',
    errorPrefix: 'Something went wrong.',
    errorHint: '',
    errorStreamDropped: 'The connection dropped. Want to try again?',
    errorRetry: 'Try again',
    errorRateLimit: 'The assistant is swamped right now. Give it a moment and try again.',
    errorServiceUnavailable: 'The service is temporarily unavailable. Please try again shortly.',
    errorGeneric: 'Something went wrong. Please send your question again.',
    productScopeLabel: 'Focus:',
    productScopeAll: 'All products',
    productScopeAria: 'Pick a product to focus on',
  },
};

export function loadInitialLang(): Language {
  if (typeof window === 'undefined') return 'id';
  const stored = window.localStorage.getItem('docagent.lang');
  return stored === 'en' ? 'en' : 'id';
}
