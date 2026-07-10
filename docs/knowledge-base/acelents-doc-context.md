---
product_id: acelents
product_name: Acelents Website (tep-web)
status: active
---

# Acelents Website (tep-web) - Feature Context & Guide Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam **website marketing + produk Acelents** (repo `tep-web`) beserta panduan fungsional, struktur navigasi, routing, serta cara menjalankannya secara lokal. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, arsitektur, dan modul-modul yang ada pada situs Acelents.

> **Catatan:** Acelents adalah produk _talent management_ (succession planning, talent mapping, dan manajemen struktur organisasi) — tagline internal "Accelerator of Talent Growth". Aplikasi ini adalah **situs publik statis** yang bertugas menjelaskan produk, menyajikan tur produk interaktif, menangkap permintaan demo (lead capture), dan menerbitkan blog. Deploy dev berada di `https://dev.acelents.com`.

---

## Tech Stack & Arsitektur

- **Framework:** Astro 5 (`output: static`) + React 19 (islands via `@astrojs/react`)
- **Bahasa:** TypeScript
- **Styling:** Tailwind CSS v4 (`@tailwindcss/postcss`) + `@tailwindcss/typography` + `tw-animate-css`
- **UI Primitives:** Radix UI + `lucide-react` (ikon), `clsx` + `tailwind-merge` (`cn` helper di `src/lib/utils.ts`)
- **Font:** Plus Jakarta Sans (`@fontsource-variable/plus-jakarta-sans`)
- **SEO:** `@astrojs/sitemap` (sitemap otomatis, halaman `/tour` di-_exclude_) + JSON-LD structured data
- **Image Optimization:** `sharp`
- **Environment Config:** `env-cmd` dengan file `.env-cmdrc` (profil `local`, `development`, `staging`, `production`)
- **Package Manager:** npm (monorepo tipis — source aplikasi ada di `apps/`)
- **Arsitektur Komponen:** Atomic Design (`atoms/` → `molecules/` → `organisms/` → `pages/`); halaman Astro di `src/pages/` bersifat _thin wrapper_ yang me-mount komponen React sebagai island (`client:load` / `client:visible`)
- **Deployment:** Static build ke `apps/dist/` (HTML/CSS/JS murni, tanpa server runtime)

### Struktur Direktori (`apps/src/`)

| Folder | Isi |
|---|---|
| `pages/` | Route Astro (`index.astro`, `tour/`, `plan-a-demo/`, `blog/`) |
| `layouts/` | `Layout.astro` (layout utama), `TourLayout.tsx` |
| `components/atoms` | `Button`, `Input`, `Select`, `Tooltip`, `Badge`, `Text`, `Heading`, dll |
| `components/molecules` | `BlogCard`, `TourModal`, `TourStepTooltip`, `PhoneInput`, `StatCard`, dll |
| `components/organisms` | `Navbar`, `Footer`, `HeroSection`, `PlanADemoForm`, `Tour*` (banyak komponen tur), dll |
| `components/pages` | `TourPage`, `PlanADemoPage`, `BlogListing` |
| `constants/` | `blog.ts`, `formOptions.ts`, `tourData.ts`, `tourOptions.ts`, `tourSteps.ts` |
| `contexts/` | `TourContext.tsx` (state tur produk) |
| `hooks/` | `useClickOutside`, `useInView`, `useScrollDirection`, `useScrollProgress` |
| `lib/` | `api.ts` (submit demo), `utils.ts` |

### Environment (`.env-cmdrc`)

| Environment | `PUBLIC_API_BASE_URL` | `SITE_URL` |
|---|---|---|
| local | `https://service-tep.dlabssaas.io` | `http://localhost:4321` |
| development | `https://service-tep.dlabssaas.io` | `https://dev.acelents.com` |
| staging | `https://servicestaging-tep.dlabssaas.io` | `https://staging.acelents.com` |
| production | `https://service-tep.odyssey.co.id` | `https://acelents.com` |

> `PUBLIC_API_BASE_URL` dipakai satu-satunya endpoint dinamis: submit form demo. `SITE_URL` menentukan origin build-time untuk sitemap + canonical URL.

---

## How to Run (Menjalankan Secara Lokal)

Sumber diambil dari repo `tep-web` branch **`development-astro`**.

### Prasyarat

- **Node 22+**
- **npm**
- **Git**

### Langkah

```bash
git clone https://github.com/dayalima/tep-web
cd tep-web

# checkout branch yang aktif dikembangkan
git checkout development-astro

# source aplikasi berada di folder apps/
cd apps
npm install
npm run dev
```

`npm run dev` menjalankan `env-cmd -e local -- astro dev`, yaitu Astro dev server dengan profil environment `local`. Situs tersedia di **`http://localhost:4321`** (port default Astro).

### Verifikasi

```bash
curl -I http://localhost:4321/
# HTTP/1.1 200 OK
```

### Script yang Tersedia (`apps/package.json`)

| Script | Fungsi |
|---|---|
| `npm run dev` | Dev server (profil `local`) |
| `npm run build` | Build statis (tanpa profil env) |
| `npm run build:dev` / `build:staging` / `build:prod` | Build per-environment via `env-cmd` → output ke `apps/dist/` |
| `npm run preview` | Preview hasil build |
| `npm run lint` / `lint:fix` | ESLint |
| `npm run format` / `format:check` | Prettier |

### Catatan Penting

- **Port 4321 bentrok** dengan frontend agent doc-agent (yang juga default Astro 4321). Jika keduanya jalan bersamaan, jalankan salah satu di port lain: `npm run dev -- --port 4322`.
- `apps/README.md` masih berisi boilerplate **Next.js** (leftover template) — abaikan, project ini murni **Astro**, bukan Next.js.
- Halaman **Tur Produk (`/tour`) hanya dapat diakses via desktop/laptop** (lebar layar besar). Di mobile ditampilkan pesan untuk beralih ke perangkat lebih besar.

---

## 1. Home (Landing Page)

Halaman utama — hal pertama yang dilihat pengunjung. Memperkenalkan Acelents, menampilkan CTA utama (Tur Produk, Jadwalkan Demo), dan menjadi gerbang ke seluruh situs.

- **Path/Route:** `/` (`src/pages/index.astro`)
- **Akses:** Publik, tanpa login.
- **Struktur Section (organisms, di-render berurutan):**
  - **HeroSection** (`client:load`) — hero utama + CTA (animasi berat di first paint).
  - **VideoSection** — video pengenalan produk.
  - **StatsSection** — metrik/angka pencapaian.
  - **OrbitalSection** — visual orbit fitur/nilai produk.
  - **FeaturesSection** — daftar fitur unggulan.
  - **WhyAcelentsSection** — alasan memilih Acelents.
  - **BlogSection** — cuplikan artikel blog terbaru.
  - **OtherServicesSection** — layanan/produk lain terkait.
  - **CTASection** — call-to-action penutup (menjadwalkan demo).

---

## 2. Product Tour (Tur Produk Interaktif)

Walkthrough interaktif produk Acelents yang memungkinkan pengunjung mencoba alur-alur kunci **tanpa perlu mendaftar/login**. Ini adalah fitur paling kompleks di situs (banyak komponen `Tour*` + `TourContext`).

- **Path/Route:** `/tour` (`src/pages/tour/index.astro`, di-mount `TourPage`)
- **Akses:** Publik, **desktop-only** (mobile menampilkan pesan pengalih perangkat).
- **State:** dikelola via `TourContext.tsx`; step & data dari `constants/tourSteps.ts`, `tourOptions.ts`, `tourData.ts`.
- **3 Alur Tur (dari `TOUR_OPTIONS`):**
  1. **Struktur Organisasi yang Informatif** (`struktur-organisasi`, 4 langkah) — melihat kondisi setiap posisi organisasi secara komprehensif; fitur filter (cabang, job-family, divisi, departemen, posisi), highlight data penting, dan menandai posisi kunci + catatan.
  2. **Succession Planning yang Objektif dan Terukur** (`succession-planning`, 7 langkah) — menemukan successor berbasis data: identifikasi posisi tanpa successor (skor "SC"), menyusun kriteria di _Position Profile_ (kompetensi, pendidikan, hard-skill, performance), mengonversi data jadi formula terukur, dan pemrosesan massal (otomatis/manual).
  3. **Mengidentifikasi Gap Setiap Karyawan** (`gap-karyawan`) — mengetahui gap karyawan terhadap kriteria posisi untuk mengarahkan pengembangan.
- **Komponen pendukung tur:** `TourWelcomeModal`, `TourSidebar`, `TourTopbar`, `TourFooter`, `TourOrganizationView` (org chart), `TourPositionProfileView`, `TourPositionDetailSheet`, `TourFilterModal`, `TourZoomControls`, `TourViewOptionsDropdown`, `TourStepTooltip`, `TourFormModal` / `TourDemoSuccessModal` (lead capture di dalam tur), `TourCompletionModal` / `TourFinalModal` / `TourSuccessModal`.
- **SOP Menjalankan Tur:**
  1. Buka `/tour` dari desktop, atau klik "Tur Produk" dari navigasi home.
  2. Pilih salah satu dari 3 alur tur pada welcome modal.
  3. Ikuti langkah demi langkah yang dipandu tooltip (`TourStepTooltip`) di atas simulasi UI produk (org chart, position profile, dll).
  4. Di akhir tur, pengguna dapat langsung mengisi form permintaan demo (`TourFormModal`) tanpa keluar dari halaman.
- **Catatan SEO:** halaman `/tour` di-_exclude_ dari sitemap (`astro.config.mjs`) namun tetap punya JSON-LD `WebPage`.

---

## 3. Plan a Demo (Lead Capture Form)

Form permintaan demo — pengunjung/prospek mengisi data untuk dihubungi tim sales. Ini satu-satunya fitur yang memanggil API backend.

- **Path/Route:** `/plan-a-demo` (`src/pages/plan-a-demo/index.astro`, di-mount `PlanADemoPage` → `PlanADemoForm`)
- **Akses:** Publik, terbuka untuk semua pengunjung.
- **API:** `POST {PUBLIC_API_BASE_URL}/rest/web/open/landing/request/demo` (via `src/lib/api.ts` → `submitDemoRequest`). Fungsi ini dipakai bersama oleh `PlanADemoForm` dan `TourFormModal`.
- **Field Payload (`DemoRequestPayload`):** `name`, `email`, `phoneNumber`, `position`, `companyName`, `companySize`, `reason`.
- **Opsi Form (`constants/formOptions.ts`):**
  - **Company Size** (`EMPLOYEE_COUNT_OPTIONS`): `<100`, `101-200`, `201-500`, `501-1000`, `>1000`.
  - **Reason / Talent Strategy** (`TALENT_STRATEGY_OPTIONS`): kesulitan menentukan suksesor posisi kritikal; sulit memantau progres pengembangan skill; hambatan memetakan pergerakan talenta; ingin konsultasi strategi manajemen talenta umum.
- **SOP Mengirim Demo:**
  1. Buka `/plan-a-demo` (atau klik "Jadwalkan Demo" dari mana saja di situs).
  2. Isi nama, email, nomor telepon (`PhoneInput`), posisi, nama perusahaan, ukuran perusahaan, dan alasan/kebutuhan.
  3. Klik submit → `submitDemoRequest` mengirim payload ke endpoint demo.
  4. Jika sukses, tampil `PlanADemoSuccess`; jika gagal, error message dari `data.info.messageEn` ditampilkan.
- **Catatan:** validasi error hanya muncul setelah submit tidak valid. Jangan submit PII asli saat testing/capture.

---

## 4. Blog

Katalog artikel + halaman baca per-artikel. Mendorong trafik organik dan narasi produk.

- **Path/Route:**
  - `/blog` (listing — `src/pages/blog/index.astro` → `BlogListing`)
  - `/blog/[slug]` (halaman artikel individual — `src/pages/blog/[slug].astro`)
- **Akses:** Publik.
- **Data:** konten/daftar artikel dari `constants/blog.ts`; komponen kartu `BlogCard` / `BlogCardLarge`, share via `ShareSection`.
- **SOP Membaca Artikel:**
  1. Buka `/blog` untuk melihat daftar artikel.
  2. Klik salah satu artikel untuk membaca di `/blog/<slug>`.
- **Catatan:** artikel individual adalah dynamic route (per-slug), tidak ada scenario capture kanonik per artikel.

---

## Layout & Navigasi

- **`Layout.astro`** — layout utama (Navbar + Footer + head/SEO), menerima props `title`, `description`, `keywords`, `hideScheduleDemo`, `hideNavbar`, `hideFooter`. Halaman `/tour` memakai `hideNavbar`/`hideFooter`/`hideScheduleDemo` untuk pengalaman full-screen.
- **`Navbar` (organism)** — navigasi utama + tombol "Jadwalkan Demo" (bisa disembunyikan).
- **`Footer` (organism)** — footer situs.
- **Astro Islands** — komponen interaktif di-hydrate selektif: `client:load` (segera, mis. Hero) vs `client:visible` (saat masuk viewport, mis. Stats/Blog) untuk performa.

---

> [!TIP]
> **Alur Umum Pengunjung Acelents:**
>
> 1. **Landing** → `/` (mengenal produk, lihat stats & fitur)
> 2. **Coba Tur Produk** → `/tour` (desktop, pilih 1 dari 3 alur: struktur organisasi / succession planning / gap karyawan)
> 3. **Jadwalkan Demo** → `/plan-a-demo` (isi form → `POST /rest/web/open/landing/request/demo`)
> 4. **Baca Blog** → `/blog` → `/blog/<slug>`
>
> Situs bersifat **statis** (tanpa auth, tanpa server runtime). Satu-satunya interaksi backend adalah pengiriman form permintaan demo. Deploy dev di `https://dev.acelents.com`, source di repo `tep-web` branch `development-astro`.
