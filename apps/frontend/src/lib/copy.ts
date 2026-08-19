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

// Type-only, so this pairs with chat.ts's `import type { Copy }` without
// creating a runtime cycle — both imports are erased at compile time.
import type { Confidence, Verdict } from './chat';

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
  // A per-DAY quota, not a momentary rate limit. Needs its own copy because
  // "wait a moment and try again" is actively wrong advice — the limit does
  // not clear until the quota resets.
  errorQuotaExhausted: string;
  errorServiceUnavailable: string;
  errorGeneric: string;
  // Shown when the agent hit its tool-round budget — a distinct situation from
  // a crash, so it gets copy that tells the user what actually helps.
  errorLoopGuard: string;
  productScopeLabel: string;
  productScopeAll: string;
  productScopeAria: string;
  // Entry gate: shown until the user picks a scope, which is what makes the
  // product filter real rather than a default nobody notices.
  gateHeading: string;
  gateSubtitle: string;
  gateAllProducts: string;
  gateAllProductsHint: string;
  gateLoading: string;
  // Backend still booting / not reachable. `just dev` starts FE and BE
  // together and the FE always wins the race, so this is the normal first
  // second of a dev session, not an exceptional failure.
  gateConnecting: string;
  gateUnreachableHeading: string;
  gateUnreachableBody: string;
  gateRetry: string;
  scopeChangeAria: string;
  composerLockedPlaceholder: string;
  citationSources: string;
  // Evidence panel — shows which retrieved passages backed the answer, with
  // both the similarity score and the keyword overlap. Rejected passages are
  // listed too: on this corpus a high score is not evidence of being on topic,
  // and seeing one thrown out is what explains the ranking.
  evidenceLabel: string;
  evidenceAria: string;
  evidenceConfidence: (level: Confidence) => string;
  evidenceUsed: (used: number, total: number) => string;
  evidenceMatches: (n: number) => string;
  evidenceScore: string;
  evidenceVerdict: (verdict: Verdict) => string;
  evidenceScopeNote: (productId: string) => string;
  // Shown when nothing cleared the bar, so the reader knows the answer was not
  // built from the passages listed below it.
  evidenceNoneNote: string;
  // Model picker + BYOK. Voice note: the key is the user's own property and we
  // do not keep it, so say that plainly rather than burying it in fine print.
  modelPickerLabel: string;
  modelPickerAria: string;
  modelKeyLabel: string;
  modelKeyPlaceholder: string;
  modelKeyHelp: string;
  modelKeySaved: string;
  modelKeyClear: string;
  modelUnavailable: (envKey: string) => string;
  modelNeedsKey: string;
  // Shown on an entry the server has no key for but the user does. Says whose
  // key pays for it, so a wrong-provider key produces an error they can explain.
  modelUsesYourKey: string;
  modelSearchPlaceholder: string;
  modelNoMatch: string;
  modelMoreAvailable: (n: number) => string;
  modelLoadFailed: string;
  modelNoneCredentialed: string;
  modelListEmpty: string;
  // Offline mode — answer from the local index without calling the provider.
  // Per request, so one person's toggle does not affect anyone else.
  offlineModeLabel: string;
  offlineModeHelp: string;
  offlineModeBadge: string;
  offlineModeLocks: string;
  // Voice input (Web Speech API). The button only renders when the browser
  // supports it, so there is no "unsupported" string to show.
  voiceLabel: string;
  voiceStopLabel: string;
  loginWithGoogle: string;
  logoutLabel: string;
  logoutAria: string;
  logoutConfirmTitle: string;
  logoutConfirmBody: string;
  logoutConfirmYes: string;
  logoutConfirmCancel: string;
  historyLabel: string;
  historyAria: string;
  historyEmpty: string;
  historyLoading: string;
  historyNewChat: string;
  // Knowledge-base submission form.
  kbAria: string;
  kbTitle: string;
  kbSubtitle: string;
  kbDocType: string;
  kbDocTypeProduct: string;
  kbDocTypeFeature: string;
  kbDocTypeRunbook: string;
  kbDocTypeHint: string;
  kbTitleField: string;
  kbTitlePlaceholder: string;
  kbSlugPreview: (name: string) => string;
  kbProduct: string;
  kbProductPlaceholder: string;
  kbProductLoading: string;
  kbContent: string;
  kbContentPlaceholder: string;
  kbRequired: string;
  kbNeedsHeading: string;
  kbDraftRestored: string;
  kbSubmit: string;
  kbSubmitting: string;
  kbCancel: string;
  kbSuccessTitle: string;
  kbSuccessBody: string;
  kbErrorTitle: string;
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
    errorQuotaExhausted:
      'Jatah pemakaian harian model sudah habis, jadi nyoba lagi sekarang nggak akan jalan. Jatahnya balik lagi besok.',
    errorServiceUnavailable: 'Layanannya lagi nggak tersedia. Coba lagi beberapa saat lagi, ya.',
    errorGeneric: 'Ada yang nggak beres. Coba kirim lagi pertanyaannya.',
    errorLoopGuard:
      'Pertanyaannya kelamaan dicari dan saya hentikan biar nggak boros. Coba persempit pertanyaannya, atau pilih fokus produk yang lebih spesifik.',
    productScopeLabel: 'Fokus:',
    productScopeAll: 'Semua produk',
    productScopeAria: 'Pilih produk yang ingin difokuskan',
    gateHeading: 'Mau tanya soal produk yang mana?',
    gateSubtitle:
      'Pilih dulu fokusnya biar jawaban saya diambil dari dokumentasi yang tepat. Nanti bisa diganti kapan aja lewat menu di atas.',
    gateAllProducts: 'Semua produk',
    gateAllProductsHint: 'Buat pertanyaan yang membandingkan beberapa produk',
    gateLoading: 'Lagi ambil daftar produk…',
    gateConnecting: 'Lagi nyambung ke server…',
    gateUnreachableHeading: 'Servernya belum bisa dihubungi',
    gateUnreachableBody:
      'Daftar produknya belum bisa diambil. Kalau kamu lagi menjalankan `just dev`, biasanya server backend-nya masih nyala — tunggu sebentar lalu coba lagi.',
    gateRetry: 'Coba lagi',
    scopeChangeAria: 'Ganti fokus produk',
    composerLockedPlaceholder: 'Pilih fokus produk dulu di atas',
    citationSources: 'Sumber',
    evidenceLabel: 'Dasar jawaban',
    evidenceAria: 'Lihat bagian dokumentasi yang jadi dasar jawaban ini',
    evidenceConfidence: (level) =>
      ({
        high: 'Cocok banget',
        medium: 'Cukup cocok',
        low: 'Cocoknya tipis',
        none: 'Nggak ada yang cocok',
      })[level],
    evidenceUsed: (used, total) => `${used} dari ${total} bagian dipakai`,
    evidenceMatches: (n) => (n === 0 ? 'nggak ada kata yang sama' : `${n} kata sama`),
    evidenceScore: 'kemiripan',
    evidenceVerdict: (verdict) =>
      ({ strong: 'Dipakai', weak: 'Cadangan', rejected: 'Dilewati' })[verdict],
    evidenceScopeNote: (productId) => `Dicari cuma di dokumentasi ${productId}.`,
    evidenceNoneNote:
      'Nggak ada bagian yang cukup nyambung sama pertanyaannya, jadi jawaban di atas nggak diambil dari dokumentasi. Angka kemiripan bisa keliatan tinggi tapi nggak berarti nyambung.',
    modelPickerLabel: 'Model',
    modelPickerAria: 'Pilih model yang dipakai buat menjawab',
    modelKeyLabel: 'API key kamu',
    modelKeyPlaceholder: 'Tempel API key di sini',
    modelKeyHelp:
      'Key-nya cuma disimpan di browser kamu dan dikirim langsung ke penyedia model. Kami nggak menyimpannya di server.',
    modelKeySaved: 'Key tersimpan di browser ini',
    modelKeyClear: 'Hapus key',
    // Points down at the key field instead of reading like a refusal — nothing
    // is blocked, the user just needs a credential for this provider.
    modelUnavailable: (envKey) => `Perlu ${envKey} — tempel key kamu di bawah`,
    modelNeedsKey: 'Tempel API key dulu buat pakai model ini',
    modelUsesYourKey: 'Pakai API key kamu — pastikan key-nya buat penyedia ini',
    modelSearchPlaceholder: 'Cari model…',
    modelNoMatch: 'Nggak ada model yang cocok',
    modelMoreAvailable: (n) => `+${n} model lain, ketik buat nyari`,
    modelLoadFailed: 'Daftar modelnya belum bisa diambil. Servernya mungkin masih nyala.',
    modelNoneCredentialed:
      'Belum ada model yang bisa dipakai dari server ini. Tempel API key kamu di bawah buat mulai.',
    modelListEmpty: 'Daftar modelnya belum kebaca.',
    offlineModeLabel: 'Mode offline',
    offlineModeHelp:
      'Jawaban dikutip langsung dari dokumentasi lokal, tanpa manggil model. Nggak makan kuota, dan cuma berlaku buat kamu.',
    offlineModeBadge: 'offline',
    offlineModeLocks: 'Selama mode offline nyala, model dan API key nggak kepakai.',
    voiceLabel: 'Tanya pakai suara',
    voiceStopLabel: 'Berhenti merekam',
    loginWithGoogle: 'Masuk dengan Google',
    logoutLabel: 'Keluar',
    logoutAria: 'Keluar dari akun',
    logoutConfirmTitle: 'Yakin mau keluar?',
    logoutConfirmBody: 'Riwayat percakapan tetap tersimpan dan bisa diakses lagi setelah masuk.',
    logoutConfirmYes: 'Ya, keluar',
    logoutConfirmCancel: 'Batal',
    historyLabel: 'Riwayat',
    historyAria: 'Buka riwayat percakapan',
    historyEmpty: 'Belum ada riwayat percakapan.',
    historyLoading: 'Memuat riwayat…',
    historyNewChat: 'Percakapan baru',
    kbAria: 'Tambah dokumen ke basis pengetahuan',
    kbTitle: 'Tambah dokumen',
    kbSubtitle: 'Dokumen masuk antrean review dulu, baru bisa dijawab agent.',
    kbDocType: 'Jenis dokumen',
    kbDocTypeProduct: 'Ringkasan produk',
    kbDocTypeFeature: 'Satu fitur',
    kbDocTypeRunbook: 'Panduan operasional',
    kbDocTypeHint: 'Isi kerangka di bawah. Satu dokumen sebaiknya membahas satu hal.',
    kbTitleField: 'Judul',
    kbTitlePlaceholder: 'misal: Fitur Login',
    kbSlugPreview: (name: string) => `Disimpan sebagai ${name}`,
    kbProduct: 'Produk',
    kbProductPlaceholder: 'Pilih produk',
    kbProductLoading: 'Memuat daftar produk…',
    kbContent: 'Isi dokumen',
    kbContentPlaceholder: 'Tulis di sini…',
    kbRequired: 'Bagian ini belum diisi.',
    kbNeedsHeading: 'Isi dokumen perlu minimal satu judul bagian (diawali #).',
    kbDraftRestored: 'Draf sebelumnya dipulihkan.',
    kbSubmit: 'Kirim untuk review',
    kbSubmitting: 'Mengirim…',
    kbCancel: 'Batal',
    kbSuccessTitle: 'Terkirim',
    kbSuccessBody: 'Dokumen menunggu review sebelum bisa dijawab agent.',
    kbErrorTitle: 'Gagal mengirim',
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
    errorQuotaExhausted:
      "The model's daily usage allowance is used up, so trying again now won't help. It resets tomorrow.",
    errorServiceUnavailable: 'The service is temporarily unavailable. Please try again shortly.',
    errorGeneric: 'Something went wrong. Please send your question again.',
    errorLoopGuard:
      'That question took too many searches, so I stopped before it got wasteful. Try narrowing it down, or pick a more specific product focus.',
    productScopeLabel: 'Focus:',
    productScopeAll: 'All products',
    productScopeAria: 'Pick a product to focus on',
    gateHeading: 'Which product are you asking about?',
    gateSubtitle:
      'Pick a focus first so my answers come from the right documentation. You can change it any time from the menu above.',
    gateAllProducts: 'All products',
    gateAllProductsHint: 'For questions that compare several products',
    gateLoading: 'Loading the product list…',
    gateConnecting: 'Connecting to the server…',
    gateUnreachableHeading: "Can't reach the server yet",
    gateUnreachableBody:
      "The product list couldn't be loaded. If you're running `just dev`, the backend is probably still starting up — give it a moment and try again.",
    gateRetry: 'Try again',
    scopeChangeAria: 'Change product focus',
    composerLockedPlaceholder: 'Pick a product focus above first',
    citationSources: 'Sources',
    evidenceLabel: 'What this is based on',
    evidenceAria: 'See the documentation passages behind this answer',
    evidenceConfidence: (level) =>
      ({
        high: 'Strong match',
        medium: 'Decent match',
        low: 'Thin match',
        none: 'No real match',
      })[level],
    evidenceUsed: (used, total) => `${used} of ${total} passages used`,
    evidenceMatches: (n) => (n === 0 ? 'no shared words' : `${n} shared word${n === 1 ? '' : 's'}`),
    evidenceScore: 'similarity',
    evidenceVerdict: (verdict) =>
      ({ strong: 'Used', weak: 'Backup', rejected: 'Skipped' })[verdict],
    evidenceScopeNote: (productId) => `Searched only ${productId}'s documentation.`,
    evidenceNoneNote:
      'Nothing came close enough to the question, so the answer above was not built from the docs. A high similarity number does not mean a passage is on topic.',
    modelPickerLabel: 'Model',
    modelPickerAria: 'Choose the model used to answer',
    modelKeyLabel: 'Your API key',
    modelKeyPlaceholder: 'Paste your API key',
    modelKeyHelp:
      'Kept in your browser only and sent straight to the model provider. We do not store it on our servers.',
    modelKeySaved: 'Key saved in this browser',
    modelKeyClear: 'Remove key',
    modelUnavailable: (envKey) => `Needs ${envKey} — paste your key below`,
    modelNeedsKey: 'Paste an API key to use this model',
    modelUsesYourKey: 'Uses your API key — make sure it is for this provider',
    modelSearchPlaceholder: 'Search models…',
    modelNoMatch: 'No models match',
    modelMoreAvailable: (n) => `+${n} more, type to search`,
    modelLoadFailed: "Couldn't load the model list. The server may still be starting up.",
    modelNoneCredentialed:
      'No models are usable from this server yet. Paste your API key below to get started.',
    modelListEmpty: 'The model list has not loaded.',
    offlineModeLabel: 'Offline mode',
    offlineModeHelp:
      'Answers are quoted straight from the local docs, with no model call. Costs no quota, and applies only to you.',
    offlineModeBadge: 'offline',
    offlineModeLocks: 'While offline mode is on, the model and API key are not used.',
    voiceLabel: 'Ask by voice',
    voiceStopLabel: 'Stop recording',
    loginWithGoogle: 'Sign in with Google',
    logoutLabel: 'Sign out',
    logoutAria: 'Sign out of your account',
    logoutConfirmTitle: 'Sign out?',
    logoutConfirmBody:
      'Your conversation history is saved and will be accessible once you sign back in.',
    logoutConfirmYes: 'Yes, sign out',
    logoutConfirmCancel: 'Cancel',
    historyLabel: 'History',
    historyAria: 'Open conversation history',
    historyEmpty: 'No conversation history yet.',
    historyLoading: 'Loading history…',
    historyNewChat: 'New chat',
    kbAria: 'Add a document to the knowledge base',
    kbTitle: 'Add a document',
    kbSubtitle: 'Documents go to a review queue before the agent can answer from them.',
    kbDocType: 'Document type',
    kbDocTypeProduct: 'Product overview',
    kbDocTypeFeature: 'Single feature',
    kbDocTypeRunbook: 'Runbook',
    kbDocTypeHint: 'Fill in the outline below. One document should cover one thing.',
    kbTitleField: 'Title',
    kbTitlePlaceholder: 'e.g. Login feature',
    kbSlugPreview: (name: string) => `Saved as ${name}`,
    kbProduct: 'Product',
    kbProductPlaceholder: 'Pick a product',
    kbProductLoading: 'Loading products…',
    kbContent: 'Document body',
    kbContentPlaceholder: 'Write here…',
    kbRequired: 'This one is still empty.',
    kbNeedsHeading: 'The body needs at least one section heading (starting with #).',
    kbDraftRestored: 'Restored your previous draft.',
    kbSubmit: 'Send for review',
    kbSubmitting: 'Sending…',
    kbCancel: 'Cancel',
    kbSuccessTitle: 'Sent',
    kbSuccessBody: 'Your document is waiting for review before the agent uses it.',
    kbErrorTitle: 'Could not send',
  },
};

export function loadInitialLang(): Language {
  if (typeof window === 'undefined') return 'id';
  const stored = window.localStorage.getItem('docagent.lang');
  return stored === 'en' ? 'en' : 'id';
}
