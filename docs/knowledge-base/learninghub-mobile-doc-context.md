---
product_id: learninghub-mobile
product_name: Learning Hub Mobile
status: active
---

# Learning Hub Mobile

Dokumen ini menjelaskan fitur-fitur utama aplikasi secara ringkas: nama fitur, fungsi, dan konten yang ditampilkan.

## 1. Home Page

### 1.1 Learning Dashboard
- Fungsi: Menampilkan ringkasan progres belajar pengguna.
- Konten:
  - Total Journey Taken
  - Total Course Taken
  - Akses ke daftar Journey Taken dan Course Taken

### 1.2 Current Activity
- Fungsi: Menampilkan aktivitas belajar yang sedang berjalan atau perlu dilanjutkan.
- Konten:
  - Nama journey
  - Nama aktivitas
  - Tipe aktivitas
  - Estimasi durasi
  - Status progres aktivitas
  - Tombol See All untuk melihat daftar lengkap

### 1.3 Your Journey (Ringkasan)
- Fungsi: Menampilkan daftar journey milik pengguna dari dashboard Home.
- Konten:
  - Judul journey
  - Deskripsi singkat
  - Jumlah course
  - Jumlah aktivitas
  - Jumlah peserta
  - Progres journey

### 1.4 Header Profil & Notifikasi
- Fungsi: Menampilkan informasi user dan akses cepat notifikasi.
- Konten:
  - Nama user
  - Foto profil
  - Informasi perusahaan/jabatan (jika tersedia)
  - Ikon notifikasi + indikator unread

### 1.5 NDA Prompt (Kondisional)
- Fungsi: Meminta persetujuan NDA sebelum lanjut menggunakan aplikasi (jika diperlukan akun tersebut).
- Konten:
  - Judul NDA
  - Isi NDA
  - Aksi Agree / Disagree

## 2. Journey Page

### 2.1 Journey List
- Fungsi: Menampilkan seluruh daftar journey yang bisa diikuti user.
- Konten:
  - Judul journey
  - Tipe journey
  - Deskripsi
  - Jumlah aktivitas
  - Jumlah course
  - Jumlah peserta
  - Progress value
  - Status lock/unlock

### 2.2 Pencarian Journey
- Fungsi: Mencari journey berdasarkan kata kunci.
- Konten:
  - Input search
  - Hasil journey sesuai keyword

### 2.3 Journey Detail
- Fungsi: Menampilkan detail journey secara lengkap dan aktivitas di dalamnya.
- Konten:
  - Banner/gambar journey
  - Deskripsi journey (read more/less)
  - Progres journey
  - Info objective
  - Daftar stage perjalanan (pre/during/post)
  - Daftar course dan aktivitas per stage
  - Daftar peserta
  - Sertifikat (jika progres 100% dan tersedia)

### 2.4 Jenis Aktivitas di Journey
- Fungsi: Menjalankan materi/aktivitas pembelajaran sesuai tipe.
- Konten:
  - Article
  - Video (general)
  - Video Interactive (H5P)
  - Video SCORM
  - Quiz + Score
  - Survey
  - Assignment (termasuk feedback)
  - Class
  - WebLink
  - Halaman konfirmasi mulai aktivitas

## 3. Forum Page

### 3.1 Forum Discussion List
- Fungsi: Menampilkan daftar diskusi/posting komunitas.
- Konten:
  - Nama pembuat post
  - Foto profil
  - Isi pesan/post
  - Lampiran (jika ada)
  - Jumlah view
  - Jumlah like
  - Jumlah komentar
  - Tanggal post

### 3.2 Filter Forum
- Fungsi: Menyaring daftar diskusi sesuai kriteria tertentu.
- Konten:
  - Filter parameter forum
  - Indikator filter aktif

### 3.3 Interaksi Forum
- Fungsi: Interaksi user terhadap post.
- Konten:
  - Like / Unlike
  - Lihat detail diskusi
  - Tambah post baru
  - Edit post sendiri
  - Hapus post sendiri

## 4. Leaderboard Page

### 4.1 Leaderboard Ranking
- Fungsi: Menampilkan peringkat user berdasarkan poin.
- Konten:
  - Daftar ranking
  - Nama user
  - Nilai/poin
  - Posisi rank

### 4.2 Filter Batch & Course
- Fungsi: Menyaring leaderboard berdasarkan batch dan course.
- Konten:
  - Dropdown batch
  - Dropdown course

### 4.3 Point Information
- Fungsi: Menampilkan informasi aturan/perhitungan poin.
- Konten:
  - Penjelasan point system sesuai filter batch/course

### 4.4 My Point Detail
- Fungsi: Menampilkan rincian poin pribadi user.
- Konten:
  - Detail sumber poin
  - Akumulasi poin user

## 5. Profile Page

### 5.1 Profile Information
- Fungsi: Menampilkan data akun user.
- Konten:
  - Foto profil
  - Nama lengkap
  - Email

### 5.2 Edit Profile
- Fungsi: Mengubah informasi profil user.
- Konten:
  - Form data profil
  - Upload/ubah foto profil

### 5.3 Change Password
- Fungsi: Mengubah password akun.
- Konten:
  - Current password
  - New password
  - Confirm new password

### 5.4 Pengaturan Tambahan
- Fungsi: Pengaturan aplikasi dari halaman profile.
- Konten:
  - Toggle tema (light/dark)
  - Logout
  - Informasi versi aplikasi

### 5.5 Akses Informasi & Legal
- Fungsi: Akses halaman bantuan dan dokumen legal.
- Konten:
  - FAQ
  - Terms of Use
  - Privacy Policy

## 6. Notification Page

### 6.1 Daftar Notifikasi
- Fungsi: Menampilkan notifikasi sistem ke user.
- Konten:
  - Pesan notifikasi
  - Waktu notifikasi
  - Status read/unread
  - Ikon tipe notifikasi

### 6.2 Read Action Notifikasi
- Fungsi: Menandai notifikasi sebagai dibaca.
- Konten:
  - Aksi baca satu notifikasi
  - Aksi Mark All as Read
  - Redirect ke fitur terkait saat notifikasi dibuka

## 7. Halaman Pendukung

### 7.1 Login
- Fungsi: Masuk ke aplikasi.
- Konten:
  - Input email
  - Input password
  - Tombol login
  - Toggle tema pada halaman login

### 7.2 Forgot Password / Reset Password
- Fungsi: Pemulihan akun saat lupa password.
- Konten:
  - Form identitas/email
  - Form reset password

### 7.3 FAQ
- Fungsi: Menjawab pertanyaan umum pengguna.
- Konten:
  - Daftar pertanyaan (expand/collapse)
  - Jawaban detail tiap pertanyaan
  - Informasi terakhir diperbarui

### 7.4 Rulebook
- Fungsi: Menampilkan aturan poin/penilaian pembelajaran.
- Konten:
  - Rule completed
  - Rule overdue
  - Poin untuk masing-masing kondisi


## Link URL Play Store dan App Store
- Link URL Play Store (Android): https://play.google.com/store/apps/details?id=id.co.odyssey.learninghubmobile
- Link URL App Store (iOS Apple): https://apps.apple.com/id/app/learning-hub-mobile-apps/id1571426588