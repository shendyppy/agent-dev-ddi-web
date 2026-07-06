---
product_id: new-assessment-center-participant
product_name: New Assessment Center (Participant)
status: active
default_url: https://dayatech.aca.dlabssaas.io
---

# New Assessment Center Participant - Feature Context & Tutorial Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam sistem **New Assessment Center Participant** beserta panduan langkah demi langkah (SOP) cara menggunakannya. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, struktur, dan modul-modul yang ada di dalam aplikasi web peserta assessment center.

> **Catatan:** Aplikasi ini adalah sisi **Participant** (peserta) dari platform Assessment Center PortrAI. Peserta mengakses aplikasi ini untuk mengerjakan simulasi assessment, termasuk fitur Chat, Email, Documents, Video Call, dan Chatbot AI — semuanya dalam batas waktu (timer) yang ditentukan.

---

## Tech Stack & Arsitektur

- **Framework:** React 18 + TypeScript + Vite
- **State Management:** Redux Toolkit (`@reduxjs/toolkit`)
- **Routing:** React Router DOM v7
- **UI Library:** Ant Design (antd v5) + Tailwind CSS v4
- **Rich Text Editor:** TipTap + TinyMCE + React Quill
- **Video Call:** LiveKit (`@livekit/components-react`, `livekit-client`)
- **Real-time:** Socket.IO Client
- **HTTP Client:** Axios (via custom `API` wrapper & `APISocket` for AI service)
- **Animasi:** Framer Motion
- **Enkripsi:** AES-JS
- **Cookie/Storage:** `js-cookie`, `store`
- **Firebase:** Push Notification & Analytics
- **Environment Config:** `env-cmd` dengan file `.env-cmdrc`
- **Arsitektur Komponen:** Atomic Design (Atoms → Molecules → Organisms)
- **Font:** Plus Jakarta Sans

### Environment

| Environment | API URL | AI API URL |
|---|---|---|
| Local / Development | `https://service.aca.dlabssaas.io` | `https://service.aca.dlabssaas.io` |
| Production | `https://service.aca.portrai.ai` | `https://service.aca.portrai.ai` |

### LiveKit (Video Call)

- **Dev:** `wss://livekit-dev.aca.dlabssaas.io`

---

## 1. Authentication (Otentikasi)

- **Path/Route:** `/auth/login`, `/auth/forgot-password`, `/auth/change-password`
- **Tujuan:** Menangani proses masuk (login), lupa kata sandi, dan ganti kata sandi peserta.
- **API Terkait:** `auth.changePassword`, `auth.initiationActivity`, `auth.getActivity`, `auth.getNda`, `auth.patchNda`
- **SOP Login:**
  1. Akses halaman `/auth/login`.
  2. Masukkan Email dan Password.
  3. Klik "Login". Jika kredensial valid, sistem akan mengarahkan peserta ke halaman **Home** (`/home`).
  4. Jika `forceChangePassword` aktif, peserta akan diarahkan ke halaman **Change Password** sebelum bisa mengakses fitur lain.

- **SOP Lupa Password:**
  1. Dari halaman login, klik link **Forgot Password**.
  2. Masukkan email terdaftar.
  3. Sistem akan mengirimkan instruksi reset password ke email.

- **SOP Ganti Password:**
  1. Akses halaman `/auth/change-password` atau `/change-password`.
  2. Masukkan **Old Password**, **New Password**, dan **Confirm Password**.
  3. Klik **Submit**. Sistem akan menampilkan notifikasi sukses/gagal.

---

## 2. Compliance & NDA (Kepatuhan & Perjanjian)

- **Path/Route:** `/compliance`, `/open/faq`, `/open/privacy-policy`, `/open/tnc`, `/open/compliance/:type`
- **Tujuan:** Menampilkan dokumen legal yang harus disetujui peserta sebelum memulai assessment.
- **API Terkait:** `compliance.getDataFAQ`, `compliance.getDataPrivacyPolicy`, `compliance.getDataTNC`
- **Catatan:** Halaman `/open/*` bersifat **publik** (tidak memerlukan login).

- **SOP Menyetujui NDA:**
  1. Setelah login pertama kali, peserta akan diarahkan ke halaman **Compliance/NDA**.
  2. Baca isi NDA yang ditampilkan.
  3. Centang checkbox persetujuan dan klik **Agree/Accept**.
  4. Sistem mencatat persetujuan melalui `auth.patchNda`.

- **SOP Melihat FAQ/Privacy Policy/TnC:**
  1. Akses langsung melalui URL publik (contoh: `/open/faq`).
  2. Halaman menampilkan konten yang diambil dari API tanpa perlu login.

---

## 3. Compatibility Check (Pengecekan Kompatibilitas)

- **Path/Route:** `/compatibility-check`
- **Tujuan:** Memeriksa kesiapan perangkat dan koneksi internet peserta sebelum memulai assessment.
- **API Terkait:** `compatibility.getCompatibilityCheckList`, `compatibility.getCompatibilityCheckListExternal`, `compatibility.updateStatusCompatibility`, `compatibility.testDownloadFile`

- **SOP Menjalankan Compatibility Check:**
  1. Akses halaman `/compatibility-check` (bisa diakses bahkan tanpa login untuk peserta eksternal).
  2. Sistem akan menjalankan serangkaian pengecekan otomatis:
     - **Koneksi Internet** — mengukur kecepatan download (dalam Mbps) melalui API `testDownloadFile`.
     - **Browser Compatibility** — memeriksa apakah browser yang digunakan didukung.
     - **Perangkat** — memverifikasi resolusi layar, webcam, dan mikrofon.
  3. Hasil pengecekan dikirim ke server melalui `updateStatusCompatibility`.
  4. Peserta dapat melanjutkan ke assessment jika semua pengecekan lulus.

---

## 4. Home (Halaman Utama)

- **Path/Route:** `/home`
- **Tujuan:** Dashboard utama peserta yang menampilkan informasi batch assessment yang sedang diikuti.
- **API Terkait:** `home.getInformation`, `home.getNotificationList`

- **SOP Melihat Informasi Home:**
  1. Setelah login, peserta otomatis diarahkan ke `/home`.
  2. Halaman menampilkan informasi assessment (nama batch, jadwal, status).
  3. Notifikasi terbaru ditampilkan dari **Notification Center** melalui `getHomeNotificationCenter`.

---

## 5. Timer & Assessment Flow (Timer & Alur Assessment)

- **Path/Route:** `/timer`, `/timer/finished`
- **Tujuan:** Mengelola countdown timer assessment, walkthrough/tutorial, dan alur mulai-selesai assessment.
- **API Terkait:** `timer.getTimerInfo`, `timer.patchStartAssessment`, `timer.patchFinishAssessment`, `timer.getDataSimulation`, `timer.checklistSimulation`, `timer.getDataPlatform`, `timer.checklistPlatform`, `timer.getDataInstruction`, `timer.checklistInstruction`, `timer.updateTimeReminderStatus`, `timer.saveWalkthrough`

- **SOP Memulai Assessment:**
  1. Dari halaman Home, peserta mengikuti alur onboarding:
     - **Step 1: Instruction** — membaca instruksi assessment (`getDataInstruction`), lalu checklist (`checklistInstruction`).
     - **Step 2: Simulation** — memahami simulasi yang akan dikerjakan (`getDataSimulation`), lalu checklist (`checklistSimulation`).
     - **Step 3: Platform** — melihat panduan platform/tools yang tersedia (`getDataPlatform`), lalu checklist (`checklistPlatform`).
     - **Step 4: Walkthrough** — mengikuti guided tour fitur-fitur aplikasi menggunakan **React Joyride** (`saveWalkthrough`).
  2. Setelah semua step selesai, peserta klik **Start Assessment** (`patchStartAssessment`).
  3. Timer mulai berjalan (countdown). Informasi timer diambil dari `getTimerInfo`.

- **SOP Assessment Selesai:**
  1. Ketika waktu habis atau peserta menyelesaikan semua tugas, assessment diakhiri melalui `patchFinishAssessment`.
  2. Peserta diarahkan ke halaman `/timer/finished` yang menampilkan **Assessment Finished** screen.
  3. Reminder waktu bisa diupdate statusnya melalui `updateTimeReminderStatus`.

---

## 6. Chat / Conversation (Percakapan)

- **Path/Route:** `/conversation`, `/conversation/:id`
- **Tujuan:** Simulasi percakapan chat antara peserta dengan aktor-aktor virtual (rekan kerja, atasan, bawahan) sebagai bagian dari assessment.
- **API Terkait:** `chat.getChatList`, `chat.getChatDetail`, `chat.sendMessage`, `chat.sendMultipleMessage`, `chat.markReadMessage`, `chat.getContactList`, `chat.getGroupList`, `chat.getConversationList`, `chat.getChatActors`

- **SOP Menggunakan Fitur Chat:**
  1. Buka menu **Conversation** dari navigasi sidebar.
  2. Sistem menampilkan daftar percakapan (`getConversationList`) dan daftar chat (`getChatList`).
  3. Pilih kontak/grup dari daftar kontak (`getContactList`, `getGroupList`) berdasarkan `levelId` dan `designId` peserta.
  4. Klik nama kontak untuk membuka detail percakapan (`getChatDetail`).
  5. Ketik pesan di kolom input dan klik **Send** (`sendMessage`).
  6. Sistem mendukung pengiriman **multiple messages** sekaligus (`sendMultipleMessage`).
  7. Pesan otomatis ditandai sebagai sudah dibaca (`markAsReadMessage`).
  8. Daftar aktor chat dapat dilihat melalui `getChatActors`.

---

## 7. Email (Simulasi Email)

- **Path/Route:** `/email`, `/email/compose`, `/email/forward/:emailId`
- **Tujuan:** Simulasi kotak masuk email untuk peserta — termasuk membaca, menulis, membalas, dan meneruskan email sebagai bagian dari assessment.
- **API Terkait:** `email.getInboxList`, `email.getSentList`, `email.getDraftList`, `email.getEmailDetail`, `email.getDraftDetail`, `email.markReadEmail`, `email.sendEmail`, `email.getAttachmentList`, `email.getDownloadAttachment`, `email.downloadEmailDocument`

- **SOP Membaca Email:**
  1. Buka menu **Email** dari navigasi sidebar.
  2. Sistem menampilkan daftar email di **Inbox** (`getInboxList`), **Sent** (`getSentList`), atau **Draft** (`getDraftList`).
  3. Klik email untuk melihat detail (`getEmailDetail`).
  4. Email otomatis ditandai sebagai sudah dibaca (`markAsReadEmail`).

- **SOP Menulis Email Baru:**
  1. Klik tombol **Compose** atau akses `/email/compose`.
  2. Pilih penerima dari daftar kontak (`getContactList`, `getGroupList`).
  3. Isi Subject dan Body email.
  4. Lampirkan file jika diperlukan (`getAttachmentList`).
  5. Klik **Send** (`sendEmail`).

- **SOP Forward Email:**
  1. Dari detail email, klik tombol **Forward** atau akses `/email/forward/:emailId`.
  2. Pilih penerima baru dan edit isi email jika perlu.
  3. Klik **Send**.

- **SOP Download Attachment:**
  1. Buka detail email yang memiliki lampiran.
  2. Klik tombol download pada attachment (`getDownloadAttachment` atau `downloadEmailDocument`).

---

## 8. Documents (Manajemen Dokumen)

- **Path/Route:** `/documents`, `/documents/detail`, `/documents/template-gallery`, `/documents/folder/:participantFolderDocId/:participantFolderDocName`, `/documents/:participantDocId/:fileMode`, `/documents/:participantDocId/read-only/:readOnly`
- **Tujuan:** Peserta dapat membuat, mengedit, mengorganisir, dan mengelola dokumen teks sebagai bagian dari tugas assessment (misalnya: menyusun memo, laporan, atau surat).
- **API Terkait:** `document.getFolderList`, `document.getDocumentListAllFiles`, `document.getDetailDocument`, `document.getContentDocument`, `document.getListFilesInFolder`, `document.createDocumentFile`, `document.putRenameFile`, `document.putHighlightText`, `document.getDetailFile`, `document.deleteFile`, `document.putContentFile`, `document.getDocumentLog`, `document.createDocumentLog`, `document.uploadDocumentImage`, `document.postCreateFolder`, `document.putRenameFolder`, `document.deleteFolder`, `document.getRecentDocument`, `document.createLogActivityOpenDocument`, `document.getReadOnlyFile`

- **SOP Melihat Daftar Dokumen:**
  1. Buka menu **Documents** dari navigasi sidebar.
  2. Sistem menampilkan daftar folder (`getFolderList`) dan semua file (`getDocumentListAllFiles`).
  3. Dokumen terbaru juga ditampilkan di bagian **Recent** (`getRecentDocument`).

- **SOP Membuat Dokumen Baru:**
  1. Klik **Template Gallery** (`/documents/template-gallery`) untuk memilih template, atau buat dokumen kosong.
  2. Sistem menyimpan dokumen baru melalui `createDocumentFile`.

- **SOP Mengedit Dokumen:**
  1. Klik dokumen dari daftar. Sistem membuka editor dengan mode sesuai parameter `:fileMode`.
  2. Editor menggunakan **TipTap** (rich text editor) atau **TinyMCE** sebagai alternatif.
  3. Fitur yang tersedia: formatting teks, tabel, highlight, gambar, dan paginasi.
  4. Perubahan disimpan melalui `putContentFile`.
  5. Gambar dalam dokumen diupload melalui `uploadDocumentImage`.

- **SOP Highlight Teks:**
  1. Pilih teks dalam dokumen.
  2. Gunakan fitur highlight untuk menandai bagian penting.
  3. Data highlight disimpan melalui `putHighlightText`.

- **SOP Mengelola Folder:**
  1. Buat folder baru melalui `postCreateFolder`.
  2. Rename folder melalui `putRenameFolder`.
  3. Hapus folder melalui `deleteFolder` (mendukung undo).

- **SOP Rename/Hapus File:**
  1. Klik menu aksi pada file.
  2. Pilih **Rename** → masukkan nama baru → simpan (`putRenameFile`).
  3. Pilih **Delete** → konfirmasi → file dihapus (`deleteFile`, mendukung undo).

- **SOP Read-Only Document:**
  1. Dokumen latar belakang (background information) ditampilkan dalam mode **read-only**.
  2. Akses melalui rute `/:participantDocId/read-only/:readOnly`.

---

## 9. Video Call (Panggilan Video)

- **Path/Route:** `/call/:roomId`
- **Tujuan:** Simulasi panggilan video antara peserta dengan aktor virtual, menggunakan **LiveKit** sebagai platform video conference.
- **API Terkait:** `call.getAIMessage`, `call.getConnection`

- **SOP Melakukan Video Call:**
  1. Peserta menerima notifikasi atau instruksi untuk melakukan panggilan.
  2. Sistem mengambil informasi koneksi melalui `getConnection` (menggunakan `roomName`).
  3. Jika koneksi berhasil, peserta masuk ke ruangan video call via LiveKit (`wss://livekit-dev.aca.dlabssaas.io`).
  4. Selama panggilan, sistem dapat menampilkan pesan AI melalui `getAIMessage`.
  5. Jika sesi panggilan tidak tersedia, sistem menampilkan pesan error.

---

## 10. Chatbot AI (Asisten AI)

- **Tujuan:** Peserta dapat berinteraksi dengan chatbot AI selama assessment untuk mendapatkan bantuan atau sebagai bagian dari skenario simulasi.
- **API Terkait:** `chatbot.sendMessage`, `chatbot.getHistoryChatList`

- **SOP Menggunakan Chatbot:**
  1. Buka fitur chatbot (biasanya melalui floating button atau panel).
  2. Ketik pertanyaan atau pesan di kolom input.
  3. Pesan dikirim ke AI service melalui streaming (`fetchWithInterceptor` ke endpoint `portrai-ai/api/v1/...`).
  4. Respons AI ditampilkan secara real-time menggunakan **React Markdown** dengan dukungan `remark-gfm`.
  5. Riwayat chat dapat dilihat melalui `getHistoryChatList` (mendukung pagination dengan parameter `before` dan `size`).

---

## 11. Guideline (Panduan)

- **Path/Route:** `/guideline`
- **Tujuan:** Menampilkan panduan atau petunjuk untuk assessment berdasarkan desain dan level peserta.
- **API Terkait:** `guideline.getDataGuideline`

- **SOP Melihat Guideline:**
  1. Buka menu **Guideline** dari navigasi sidebar.
  2. Sistem menampilkan konten panduan berdasarkan `designId` dan `levelId` peserta.

---

## 12. Proctoring (Pengawasan)

- **Tujuan:** Mengambil screenshot/foto peserta secara periodik selama assessment berlangsung untuk keperluan pengawasan integritas.
- **API Terkait:** `proctoring.uploadProctoring`

- **Cara Kerja:**
  1. Sistem secara otomatis menangkap gambar dari webcam peserta.
  2. Gambar di-encode ke **Base64** lalu dikirim ke server bersama informasi `menuUrl` (halaman yang sedang dibuka peserta).
  3. Jika upload gagal, sistem melakukan **retry** otomatis (max 1 retry dengan delay 2 detik).

---

## 13. Action Logging (Pencatatan Aktivitas)

- **Tujuan:** Mencatat seluruh aktivitas peserta selama assessment untuk keperluan analisis dan audit.
- **API Terkait:** `actionLog.postActions`

- **Cara Kerja:**
  1. Setiap aksi peserta (buka halaman, klik menu, buka dokumen, dll) dicatat sebagai log.
  2. Log hanya dikirim jika peserta sudah login (mengecek `userData`).
  3. Data log dikirim melalui `loggingActivities`.

---

## 14. Notification (Notifikasi)

- **Tujuan:** Mengirim notifikasi real-time ke peserta selama assessment (misalnya: email baru, chat baru, pengumuman).
- **API Terkait:** `chat.sendMessage` (digunakan juga untuk dummy notification)
- **Teknologi:** Firebase Cloud Messaging + Socket.IO

---

## Redux Store Structure

Berikut adalah daftar slice Redux yang mengelola state aplikasi:

| Slice Name | Key di Store | Keterangan |
|---|---|---|
| `cookiesReducer` | `cookiesRedux` | Manajemen cookies consent |
| `loadingReducer` | `loadingRedux` | State loading global |
| `userReducer` | `user` | Data user, auth token, authorization status |
| `notificationReducer` | `notification` | State notifikasi |
| `chatReducer` | `chat` | State chat/conversation |
| `emailReducer` | `email` | State email (inbox, sent, draft) |
| `documentReducer` | `documentRedux` | State manajemen dokumen |
| `internetReducer` | `internetRedux` | Status koneksi internet |
| `compatibilityReducer` | `compatibilityRedux` | State compatibility check |
| `platformReducer` | `platformRedux` | State info platform |
| `simulationReducer` | `simulationRedux` | State data simulasi |
| `timerReducer` | `timerRedux` | State countdown timer assessment |
| `settingReducer` | `settingRedux` | State pengaturan aplikasi |
| `guidelineReducer` | `guidelineRedux` | State panduan/guideline |
| `instructionReducer` | `instructionRedux` | State instruksi assessment |
| `walktroughReducer` | `walkthroughRedux` | State walkthrough/tutorial |
| `chatbotReducer` | `chatbotRedux` | State chatbot AI |
| `callReducer` | `callRedux` | State video call |

---

## Layout System

Aplikasi memiliki dua layout utama:

1. **Auth Layout** (`/auth/*`) — Layout untuk halaman login, forgot password, dan change password. Tanpa sidebar dan header.
2. **Main Layout** (semua halaman lain) — Layout utama dengan sidebar navigasi, header, dan area konten.

### Alur Otorisasi pada Layout:
- Jika user **belum login** dan bukan di halaman auth/compliance/compatibility → redirect ke `/auth/login`.
- Jika user login tapi `forceChangePassword = true` → redirect ke `/auth/change-password`.
- Jika user sudah login dan authorized → render layout utama dengan konten.
- Saat ada proses upload background → tampilkan indikator "Uploading videos" di pojok kanan bawah untuk mencegah user menutup tab.

---

## Komponen UI (Atomic Design)

### Atoms (Komponen Dasar)
| Komponen | Fungsi |
|---|---|
| `Alert` | Notifikasi alert global (`showAlertNotification`) |
| `Avatar` | Tampilan avatar user |
| `Button` | Tombol standar |
| `ButtonBack` | Tombol kembali |
| `ButtonBackPage` | Tombol kembali ke halaman sebelumnya |
| `ErrorState` | Tampilan state error |
| `Icons` | Koleksi ikon custom |
| `LoadingGlobal` | Indikator loading full-screen |
| `Modal` | Dialog modal dasar |
| `Popover` | Popover/tooltip |
| `Typography` | Komponen teks standar |

### Molecules (Komponen Gabungan)
| Komponen | Fungsi |
|---|---|
| `CookieConsent` | Banner persetujuan cookies |
| `Drawer` | Panel drawer slide-in |
| `DrawerDetailFile` | Drawer khusus detail file dokumen |
| `ModalNda` | Modal persetujuan NDA |
| `PageHeader` | Header halaman dengan judul dan navigasi |

### Organisms (Komponen Kompleks)
| Komponen | Fungsi |
|---|---|
| `CustomTable` | Tabel data dengan fitur sorting dan filtering |
| `Modal` | Modal kompleks (konfirmasi, form, dll) |

---

## Halaman Error

- **404 Not Found** (`/*`) — Ditampilkan saat route tidak ditemukan.
- **500 Internal Server Error** — Ditampilkan sebagai `errorElement` saat terjadi error di dalam route tree.

---

> [!TIP]
> **Alur Umum Peserta Assessment:**
>
> 1. **Login** → `/auth/login`
> 2. **Setuju NDA** → `/compliance`
> 3. **Compatibility Check** → `/compatibility-check`
> 4. **Baca Instruksi & Walkthrough** → `/timer` (onboarding steps)
> 5. **Mulai Assessment** → Timer mulai berjalan
> 6. **Kerjakan Simulasi** → Chat (`/conversation`), Email (`/email`), Documents (`/documents`), Video Call (`/call/:roomId`), Chatbot AI
> 7. **Guideline** → `/guideline` (referensi panduan)
> 8. **Assessment Selesai** → `/timer/finished`
>
> Selama proses assessment berlangsung, sistem secara otomatis melakukan **proctoring** (pengawasan via webcam) dan **action logging** (pencatatan aktivitas peserta).
