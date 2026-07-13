---
product_id: engauge-cms
product_name: Engauge
status: active
---

# Engauge - Feature Context & Tutorial Document

Dokumen ini berisi rangkuman fitur beserta panduan langkah demi langkah (SOP) untuk mengelola role pengguna dan aktivasi akun di dalam sistem **Engauge**. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, aturan bisnis, dan langkah penanganan masalah pada modul ini.

---

## 1. Manajemen Akses & Role Pengguna (User Role Management)

Modul ini digunakan untuk mendistribusikan hak akses (role) kepada karyawan dan memicu proses aktivasi akun baru.

### A. Manage User Role (`Master Data → Manage User Role`)

- **Tujuan:** Menambahkan role baru kepada employee pada project Engauge dan mengirim email aktivasi akun apabila user belum pernah melakukan aktivasi sebelumnya.
- **SOP Menambah User Role:**
  1. Login sebagai Admin.
  2. Buka menu **Master Data** $\rightarrow$ **Manage User Role**.
  3. Klik tombol **New User Role**.
  4. Pilih company (contoh: `Optik Melawai`).
  5. Pilih employee yang akan ditambahkan role-nya.
     > **Catatan:** Jika employee belum tersedia, tambahkan employee terlebih dahulu ke dalam sistem.
  6. Pilih role yang diinginkan (contoh: `Admin Engauge Default`).
  7. Klik tombol **Save**.

### B. Send Activation Email

- **Tujuan:** Mengirimkan tautan aktivasi untuk pengguna baru agar dapat membuat kata sandi dan mengakses sistem.
- **SOP Mengirim Email Aktivasi:**
  1. Cari email employee yang baru ditambahkan pada tabel **User Role List**.
  2. Pada kolom aksi, klik tombol atau ikon **Send Mail to User**.

---

## 2. Hasil yang Diharapkan (Expected Result)

### A. User Belum Pernah Aktivasi

- User menerima email bertajuk `Activate Account`.
- User membuat password baru melalui link unik yang dikirimkan ke email tersebut.
- User berhasil login ke dalam aplikasi Engauge menggunakan password yang baru dibuat.

### B. User Sudah Pernah Aktivasi

- User tidak perlu melakukan proses aktivasi ulang.
- Cukup lakukan refresh halaman atau login ulang ke sistem.
- Role baru yang didelegasikan akan langsung aktif dan muncul pada akun user.

---

## 3. Aturan Bisnis (Business Rules)

- **Batasan Email:** Satu email hanya dapat digunakan dan terdaftar pada satu company.
- **Prasyarat Employee:** Employee harus sudah terdaftar di dalam sistem sebelum role-nya dapat ditambahkan.
- **Kondisi Aktivasi:** Email aktivasi hanya diperlukan dan hanya akan diproses untuk user yang belum pernah melakukan aktivasi akun sebelumnya.

---

## 4. Penanganan Masalah & FAQ (Troubleshooting & FAQ)

### A. Troubleshooting

- **Employee tidak muncul pada list**
  - **Cause:** Employee belum terdaftar pada company yang dipilih.
  - **Solution:** Daftarkan employee tersebut terlebih dahulu ke dalam company yang bersangkutan melalui modul manajemen employee terkait.
- **Role baru tidak muncul setelah ditambahkan**
  - **Cause:** User masih menggunakan session atau data perambahan yang lama.
  - **Solution:** Refresh halaman web atau lakukan _logout_ kemudian login kembali ke akun.
- **Email aktivasi tidak diterima**
  - **Investigation:** Pastikan penulisan email sudah benar, periksa folder Spam/Junk pada kotak masuk email user, atau klik kembali tombol **Send Mail to User**.

### B. FAQ

- **Apakah user perlu aktivasi ulang ketika mendapatkan role baru?**
  Tidak. Jika user sudah pernah melakukan aktivasi sebelumnya, cukup lakukan refresh halaman atau login ulang agar hak akses baru dapat diterapkan.
