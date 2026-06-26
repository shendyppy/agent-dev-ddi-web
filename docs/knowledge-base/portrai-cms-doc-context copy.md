# PortrAI CMS - Feature Context & Tutorial Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam sistem **PortrAI CMS** beserta panduan langkah demi langkah (SOP) cara menggunakannya. Dokumen ini dirancang sebagai *context document* untuk membantu agent AI memahami kapabilitas, struktur, dan modul-modul yang ada di dalam aplikasi ini.

---

## 1. Authentication (Otentikasi)
- **Path/Route:** `/auth`
- **Tujuan:** Menangani proses masuk (login), pemulihan kata sandi, dan otorisasi.
- **SOP Login:**
  1. Akses halaman root `/` atau `/auth/login`.
  2. Masukkan Email dan Password.
  3. Klik "Login". Jika kredensial valid, sistem akan mengarahkan pengguna ke halaman Dashboard berdasarkan role-nya.

## 2. Dashboard
- **Path/Route:** `/dashboard`
- **Tujuan:** Memberikan ringkasan informasi (overview) mengenai aktivitas di dalam PortrAI.
- **SOP Melihat Statistik:**
  1. Buka menu Dashboard dari navigasi.
  2. Sistem akan menampilkan metrik seperti jumlah proyek berjalan, total partisipan, dan jadwal assessment terdekat. Anda dapat menggunakan filter rentang waktu (jika tersedia) untuk melihat data spesifik.

---

## 3. Manajemen Klien & Perusahaan (Company & Client Management)
Modul ini digunakan untuk mengelola data perusahaan klien dan proyek-proyek terkait.

### A. Manage Company (`/manage-company`, `/companies`)
- **Tujuan:** Mengelola data perusahaan secara umum.
- **SOP Menambah Company:**
  1. Buka menu **Manage Company**.
  2. Klik tombol **Add New Company**.
  3. Isi form informasi perusahaan (Nama, Industri, Alamat, Email Kontak, dll).
  4. Klik **Save/Submit**. Sistem akan memunculkan popup konfirmasi, klik "Yes/Ok".

### B. Manage Company Clients (`/manage-company-clients`)
- **Tujuan:** Mengelola user atau perwakilan dari perusahaan klien tersebut (Admin Client).
- **SOP Menambah Client User:**
  1. Buka menu **Manage Company Clients**.
  2. Klik **Add New**.
  3. Isi data form (Nama, Email, Nomor Telepon).
  4. Pilih asal perusahaan (Company) yang telah didaftarkan sebelumnya.
  5. Simpan data.

---

## 4. Manajemen Pengguna & Karyawan (User & Role Management)
Modul untuk mengatur siapa saja yang memiliki akses ke dalam CMS beserta hak akses mereka (RBAC).

### A. Manage Employee (`/manage-employee`, `/all-employees`)
- **Tujuan:** Mengelola staf / karyawan internal.
- **SOP Menambahkan Employee:**
  1. Buka menu **Manage Employee**.
  2. Klik tombol **Add New Employee**.
  3. Isi informasi pekerjaan: *Personnel Number*, pilih *Company* (terkunci jika login sebagai admin client), *Division*, *Position*, *Email*, dan *Employment Status*.
  4. Isi informasi pribadi: Nama Lengkap, Tanggal Lahir, Nomor Telepon, Gender, Pendidikan, dan Alamat.
  5. (Opsional) Unggah foto profil karyawan.
  6. Klik **Save** -> Konfirmasi persetujuan -> Karyawan berhasil ditambahkan.

### B. Manage Assessor (`/manage-assessor`, `/assessor`)
- **Tujuan:** Mengelola akun Assessor yang bertugas menilai partisipan.
- **SOP Menambahkan Assessor:**
  1. Buka menu **Manage Assessor**.
  2. Klik tombol **Add New Assessor**.
  3. Isi data kredensial assessor (Email, Nama, Kualifikasi).
  4. Tentukan *status* keaktifan assessor.
  5. Simpan data.

### C. Manage Role & User Role (`/manage-role`, `/manage-user-role`)
- **Tujuan:** Membuat tingkatan hak akses dan mendistribusikannya ke user.
- **SOP Assign Role ke User:**
  1. Buka **Manage User Role**.
  2. Cari user (employee/client) yang ingin diubah role-nya.
  3. Klik Edit.
  4. Pilih *Role* yang sesuai dari dropdown (misal: Superadmin, Client Admin, Assessor).
  5. Simpan perubahan.

---

## 5. Manajemen Proyek & Assessment (Project & Assessment Management)
Modul inti untuk menjalankan PortrAI. Terletak di folder `src/pages/manage-project/`.

### A. Project List (`/project`)
- **Tujuan:** Membuat proyek (event) assessment.
- **SOP Membuat Project Baru:**
  1. Buka menu **Project**.
  2. Klik **Add Project**.
  3. Masukkan Detail Proyek (Nama Proyek, Tanggal Mulai, Tanggal Berakhir).
  4. Pilih Klien Perusahaan yang berkaitan dengan proyek tersebut.
  5. Setelah disimpan, Anda dapat melanjutkan untuk menambahkan *Batch* dan *Assessor* ke dalam proyek ini.

### B. Participants (`/participants`)
- **Tujuan:** Mengelola peserta yang akan di-assess, serta mengundang mereka ke Web PortrAI Participant.
- **SOP Cara Mengundang Participant Mengerjakan Simulasi / Soal di Web PortrAI Participant:**

  Terdapat dua skenario alur kerja berdasarkan jenis *Company* (Internal vs External):
  
  **1. Untuk Participant Internal Company:**
  - **Langkah 1:** Input data participant (sebagai karyawan) melalui menu **Manage Employee** terlebih dahulu.
  - **Langkah 2:** Masuk ke menu **Manage Project**. Buat project baru jika belum ada. Jika project sudah ada, klik tombol **Detail** di baris tabel project yang sesuai.
  - **Langkah 3:** Di dalam detail project, buat **Batch** jika belum ada. Jika batch sudah ada, klik tombol **Detail** di baris tabel batch tersebut.
  - **Langkah 4:** Tambahkan participant (add participant) ke dalam batch tersebut.
  - **Langkah 5:** Setelah berhasil ditambahkan ke batch, kirimkan email ke participant tersebut. Melalui email inilah participant akan mendapatkan akses / link untuk mengerjakan simulasi di Web PortrAI Participant.

  **2. Untuk Participant External Company:**
  - Berbeda dengan internal, participant eksternal **tidak perlu diinput** di menu Manage Employee terlebih dahulu.
  - Anda bisa langsung menuju menu/halaman **Manage Client Project** sisanya seperti pada langkah di internal company, lalu ke **Participant** dan langsung menambahkan data participant-nya di sana, kemudian langsung mengirimkan undangan (email).

---

## 6. Pelaporan (Reporting)
- **Path/Route:** `/reports`, `/report`
- **Tujuan:** Men-generate dan mengunduh hasil penilaian assessment.
- **SOP Generate Report:**
  1. Buka menu **Reports**.
  2. Pilih *Project* dan *Batch* yang telah selesai dinilai oleh Assessor.
  3. Pilih Partisipan yang ingin dibuatkan laporannya.
  4. Klik tombol **Generate/Download Report**. Sistem akan mengekspor dokumen berupa PDF atau Excel.

---

## 7. Pengaturan Sistem & Aplikasi (System Settings & Config)
Modul untuk konfigurasi dinamis yang mengatur *behavior* sistem.

### A. Template Email & Notifikasi (`/email-template`, `/notification-template`)
- **Tujuan:** Mengatur pesan teks otomatis.
- **SOP Mengedit Template:**
  1. Buka menu **Email Template** atau **Notification Template**.
  2. Pilih jenis template yang ingin diedit (misal: *Welcome Email*, *Reset Password*).
  3. Klik ikon Edit (Pensil).
  4. Sesuaikan isi teks menggunakan variabel dinamis (contoh: `{{name}}`).
  5. Simpan template.

### B. Application Config (`/application-config`) & Menu (`/manage-menu`)
- **Tujuan:** Mengubah settingan global dan struktur menu.
- **SOP Menambah Menu Navigasi:**
  1. Buka **Manage Menu**.
  2. Tambahkan node menu baru, tentukan Icon, Route URL, dan Role apa saja yang berhak melihat menu tersebut.
  3. Simpan agar sidebar ter-update otomatis.

---

## 8. Kepatuhan & Legal (Compliance & Legal)
Modul dokumen legal (`/manage-privacy-policy`, `/manage-tnc`, `/manage-nda`, `/manage-faq`).
- **SOP Mengubah Dokumen Legal:**
  1. Pilih salah satu menu (contoh: **Manage NDA**).
  2. Anda akan melihat halaman Rich Text Editor.
  3. Ubah klausul perjanjian sesuai kebutuhan legal terbaru.
  4. Klik **Publish/Save**. Perubahan akan langsung berdampak pada halaman *approval* yang dilihat partisipan atau assessor saat pertama kali login.

---
> [!TIP]
> **Pola Operasi Standar (CRUD Pattern):**
> Sebagian besar modul di dalam CMS ini mengikuti pola UI yang seragam.
> - **Read:** Halaman awal menampilkan tabel (*List/Datatable*) yang bisa difilter dan dicari.
> - **Create:** Tombol biru "Add New..." selalu ada di pojok kanan atas tabel.
> - **Update:** Aksi Edit (ikon pensil) berada di kolom *Action* paling kanan tabel.
> - **Delete/Deactivate:** Aksi hapus atau nonaktifkan (ikon tempat sampah / toggle) berada di sebelah tombol Edit.
