# LokerKerja – CV Intelligence & Safe Apply Kit

> **Tagline:** “Verifikasi dulu, tailor cepat, kirim rapi—tanpa spam.”
> **Scope repo ini:** paket Python **`cv_handler`** (parser CV async + robust) + **API tipis** siap dipanggil web-app.

---

## Visi

Merdekakan pencari kerja dari **loker palsu** & **lamaran generik**.
Alih-alih mass-email yang rawan **spam & suspend**, LokerKerja membantu **memvalidasi lowongan**, **membaca CV**, **men-tailor** dokumen ATS-friendly, dan **menyusun draft kirim** yang patuh aturan.

## Misi

1. **Akurasi & Keamanan data** — parsing CV deterministik dengan validasi schema, logging terukur, guardrails PII.
2. **Kecepatan ke nilai** — 60 detik dari **CV/lowongan → draft siap kirim**.
3. **Patuh platform** — bukan “blast sender”; kita siapkan **draft** atau **paste-kit** untuk portal/ATS.

## Komponen Utama

* **`cv_handler` (library)**
  Async pipeline PDF/Gambar → OCR (optional) → LLM parse → **JSON Profile stabil**
  Fitur kunci:

  * OCR autoscale (gambar/scan) via **UNLI** Vision.
  * Parsing & repair JSON via **LUNOS** (OpenAI-compatible).
  * **Schema Pydantic** + normalisasi tanggal (EN/ID), **`duration_months`**.
  * Hitung **`total_duration_months`** + `total_duration` (human-readable).
  * Cache + TTL, retry + backoff, circuit breaker, JSON logging.
  * Fungsi **bytes-friendly** untuk dipanggil web-app (tanpa I/O disk permanen).

* **`jobscraper` (library)**
  Smart job search & matching dengan JobSpy integration:
  * Multi-platform job scraping (LinkedIn, Indeed, dll).
  * AI-powered CV-to-job matching menggunakan embeddings.
  * Scam detection untuk keamanan pencari kerja.
  * Position inference dari CV untuk job targeting.

* **Email & Subscription System**
  Powered by **Mailry.co** untuk job alerts & notifications:
  * Kirim hasil job search langsung ke email user.
  * Job alert subscription (daily/weekly/realtime).
  * Personalized job recommendations berdasarkan CV & preferences.
  * Newsletter automation dengan scheduler background.

* **API contoh (FastAPI)** – endpoint lengkap untuk CV parsing, job search, matching, dan email integration.

> Sponsor alignment: **Lunos** (LLM gateway + analytics), **UNLI** (auto model routing + vision), & **Mailry** (email delivery + automation).

---

## Struktur Repo (direkomendasikan)

```
.
├─ .env
├─ pyproject.toml
├─ README.md
├─ requirements.txt
└─ src/
   ├─ cv_handler/                # paket utama
   │  ├─ __init__.py            # export read_cv_async, read_cv_from_bytes_async
   │  ├─ cli.py                 # optional CLI entry-point
   │  ├─ config.py              # load .env, inisiasi AsyncOpenAI clients
   │  ├─ schema.py              # Pydantic models
   │  ├─ reader.py              # pipeline utama (modular, async)
   │  ├─ provider_lunos.py      # LUNOS chat calls + JSON repair
   │  ├─ provider_unli.py       # UNLI vision OCR
   │  ├─ utils_dates.py         # parser tanggal EN/ID + humanize
   │  ├─ utils_pdf.py           # pdfminer/pymupdf helpers
   │  ├─ utils_io.py            # sha256, base64 helpers
   │  ├─ utils_cache.py         # cache TTL
   │  └─ logutil.py             # JSON logger
   └─ LokerKerja_api/           # contoh web API
      └─ main.py                # FastAPI app
```

---

## Setup

### 1) Dependensi

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
# atau mode paket:
pip install -e .
```

### 2) Konfigurasi `.env`

```ini
# === AI & CV Processing ===
LUNOS_API_KEY=sk-...
LUNOS_BASE_URL=https://api.lunos.tech/v1

UNLI_API_KEY=sk-...         # wajib untuk OCR (gambar / PDF scan)
UNLI_BASE_URL=https://api.unli.xyz

# === Email Service (Mailry) ===
MAILRY_API_KEY=your_mailry_api_key_here
MAILRY_BASE_URL=https://api.mailry.co/ext
MAILRY_SENDER_EMAIL_ID=your_sender_email_id_from_mailry
MAILRY_WEBHOOK_SECRET=your_webhook_secret_for_verification

# === App Config ===
APP_ID=LokerKerja-backend
```

> **Note:** 
> - Tanpa `UNLI_API_KEY`, file **searchable PDF** tetap bisa diparse (tanpa OCR). Untuk scan/gambar → butuh UNLI.
> - Tanpa `MAILRY_API_KEY`, job search tetap jalan, tapi email & subscription features tidak aktif.
> - Copy `env.example` ke `.env` dan isi dengan API keys yang valid.

---

## Cara Pakai

### A) CLI

Setelah `pip install -e .`:

```bash
cv-handler "/path/CV.pdf" --no-cache
cv-handler "/path/CV_scan.jpg" --force-ocr --pages 1-3
# atau tanpa entry-point:
python -m cv_handler.cli "/path/CV.pdf"
```

### B) API Server

```bash
# Start main API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
# atau gunakan script:
./start_api.bat    # Windows
./start_api.sh     # Linux/Mac

# Start job alert scheduler (background service)
python src/scheduler.py
# atau gunakan script:
./start_scheduler.bat    # Windows
./start_scheduler.sh     # Linux/Mac
```

**Main Endpoints:**

* `POST /api/cv/parse` - CV parsing & analysis
* `POST /api/cv/infer-position` - AI position inference dari CV
* `POST /api/jobs/search` - Job search via JobSpy
* `POST /api/jobs/match` - CV-to-job matching dengan AI
* `POST /api/jobs/verify` - Scam detection untuk job postings
* `POST /api/jobs/smart-discovery` - Combined workflow (infer → search → match)
* `POST /api/jobs/smart-discovery-with-email` - Smart discovery + email delivery

**Mailry Integration Endpoints:**

* `GET /api/mailry/emails` - List sender emails
* `POST /api/mailry/send` - Send email via Mailry
* `POST /api/mailry/upload-attachment` - Upload file attachments
* `POST /api/mailry/webhook` - Webhook untuk email replies

**Subscription Management:**

* `POST /api/subscriptions` - Create/update job alert subscription
* `GET /api/subscriptions/me` - Get user subscription
* `PATCH /api/subscriptions/{id}` - Update subscription preferences
* `GET /api/subscriptions/unsubscribe` - One-click unsubscribe

**Frontend Demo:**

* Open `frontend_demo.html` in browser untuk complete workflow testing
* Features: CV upload, AI position suggestions, job discovery, email alerts, subscription management

### C) Dari kode Python (web-app / worker)

```python
import asyncio, json
from cv_handler import read_cv_from_bytes_async

data = open("CV.pdf","rb").read()
profile, meta, flags = asyncio.run(
    read_cv_from_bytes_async(data, filename="CV.pdf", pages="1-3")
)
print(json.dumps(profile, indent=2, ensure_ascii=False))
```

### C) API contoh (FastAPI)

```bash
uvicorn LokerKerja_api.main:app --reload
# POST /api/cv/parse (form-data: file)
```

**Response (ringkas):**

```json
{
  "req_id": "uuid-...",
  "profile": {
    "name": "John Doe",
    "contacts": { "email": "...", "phone": "+62...", "location": "...", "links": [] },
    "summary": "...",
    "skills": ["python","sql","tableau", "..."],
    "experience": [
      {"company":"PT X","role":"QA Intern","start":null,"end":null,"duration_months":4,"bullets":["..."]}
    ],
    "education": [...],
    "certs": [],
    "total_duration_months": 16,
    "total_duration": "1 tahun 4 bulan",
    "__features": {
      "skills_norm": [...],
      "years_total": 1.3,
      "latest_role": "QA Intern",
      "latest_company": "PT X",
      "confidence": 0.9
    }
  },
  "meta": {
    "ocr_ms": "1412.8 ms (+render 210.2 ms)",
    "parse_ms": "8210.5 ms",
    "fix_ms": "0.0 ms",
    "parse_model": "google/gemma-3-12b-it",
    "fix_model": "google/gemma-3-12b-it",
    "ocr_model": "auto",
    "total_ms": "9835.6 ms"
  },
  "from_cache": false
}
```

---

## Arsitektur Teknis

* **I/O async end-to-end**: OpenAI Async SDK; CPU-bound (pdfminer/pymupdf) dialihkan via `asyncio.to_thread`.
* **Reliability**: Tenacity **retry + backoff**, **circuit breaker** (counter sederhana).
* **Validation**: Pydantic schema; reparasi JSON via 2-pass LLM (strict → repair).
* **Tanggal**: parser EN/ID (short/long/“YYYY Month”/“Month YYYY”/“MM/YYYY”/“YYYY-MM”), dukung “Now/Present/Sekarang”.
* **Durasi**: `duration_months` (ekstrak dari teks seperti “4 months/4 bulan”); total **akumulatif** dari `start/end` atau `duration_months`.
* **Observability**: JSON logging per tahap (`req_id`, ms, model).
* **Cache**: `.cache/` + TTL (default 7 hari) berdasarkan SHA-256 file + parameter pipeline.

---

## Privasi & Keamanan (ringkas)

* **PII guard**: masking nomor telepon di JSON; log tanpa PII berlebih.
* **No file persistence**: input via API diproses dari **bytes** ke file temp, lalu **dihapus**.
* **Config**: API keys via `.env`, jangan commit.
* **Rate control**: semaphore + circuit breaker mencegah overrun provider.

---

## Testing & QA

* **Golden files**: 5 CV searchable + 5 scan; snapshot JSON `profile`.
* **Unit**: tanggal EN/ID, `duration_months`, total durasi, validasi schema.
* **Integration**: end-to-end parsing dengan dummy providers (atau mode “text only”).

> **Command ide:** tambahkan `tests/` + `pytest` (belum termasuk default).

---

## Roadmap & Status

**✅ Completed (Minggu 1-4)**

* ✅ **CV Handler**: Async PDF/image parsing dengan OCR (UNLI) + LLM (Lunos)
* ✅ **JobSpy Integration**: Multi-platform job scraping (LinkedIn, Indeed, dll)
* ✅ **AI Job Matching**: CV-to-job similarity menggunakan embeddings
* ✅ **Scam Detection**: Heuristic + LLM analysis untuk job safety
* ✅ **Position Inference**: AI-powered role suggestions dari CV
* ✅ **Mailry Integration**: Email delivery untuk job results & alerts
* ✅ **Subscription System**: Personalized job alerts (daily/weekly/realtime)
* ✅ **Background Scheduler**: Automated job discovery & email notifications
* ✅ **Frontend Demo**: Complete workflow dengan modern UI
* ✅ **API Documentation**: OpenAPI/Swagger dengan comprehensive endpoints

**🚧 In Progress (Minggu 5-6)**

* [ ] **ATS Optimizer** – CV bullets rewrites + checklist ATS
* [ ] **Apply Draft** – generator `.eml` + Gmail compose URL prefilled
* [ ] **Analytics Dashboard** – user engagement, job match success rates
* [ ] **Enhanced Scam Detection** – company verification, salary range validation

**🔮 Future (Minggu 7+)**

* [ ] **Inbox Coach** – parser undangan interview, autoresponse sopan, phishing detector
* [ ] **Multi-tenant & Auth** – JWT authentication untuk web-app production
* [ ] **Paste Kit** – optimized summaries untuk job portals (600-900 chars)
* [ ] **Mobile App** – React Native atau Flutter untuk mobile experience
* [ ] **Metrics & Monitoring** – Prometheus metrics + OpenTelemetry traces

---

## Devil’s Advocate (Reality Checks)

* **Mass email?** No. Spam & reputasi domain bikin risk. Kita siapkan **draft**, bukan blast.
* **OCR akurasi?** OCR ≠ ground truth; tetap tampilkan hasil & izinkan edit user.
* **Tanggal hilang?** Jangan halu. Pakai `duration_months`, tampilkan warning “pertimbangkan menambah periode”.
* **Biaya LLM/OCR?** Batasi halaman, autoscale gambar, cache hasil, fallback model hemat.

---

## Konfigurasi Penting

* **ENV**

  * `LUNOS_API_KEY` – wajib untuk LLM parsing.
  * `UNLI_API_KEY` – untuk OCR (gambar / PDF non-searchable).
  * `APP_ID` – label analytics LUNOS.
* **CLI flags**

  * `--force-ocr` – paksa OCR walau PDF searchable.
  * `--pages` – “1-3” atau “1,3”.
  * `--max-pages` & `--scale` – kontrol latency/biaya.
  * `--no-cache`, `--ttl-days`.

---

## Integrasi Web-App (ringkas)

* Panggil `read_cv_from_bytes_async` dari controller (FastAPI/Flask/Django).
* Perhatikan **timeout** (HTTP 60–90s) & **upload size limit** (12–16 MB).
* Simpan hanya `profile` & minimal metadata; jangan simpan file pengguna kecuali dengan **consent**.

---

## Kontribusi

* Ikuti gaya import absolut (`cv_handler.*`), PEP8 yang wajar.
* PR kecil: fokus per modul (tanpa mixed concerns).
* Tambah test untuk setiap perubahan parsing/normalisasi.

---

## Lisensi

Tentukan sesuai strategi (MIT/Apache-2.0). Default: MIT (opsional).

---

## Acknowledgments

* **Lunos** – unified API untuk beberapa model + fallback, analytics.
* **UNLI** – auto model routing + vision (OCR via chat).
* **JobSpy** – scraping sumber loker (akan diintegrasikan dalam modul rekomendasi).

---

## Lampiran – JSON Schema (ringkas)

```json
{
  "name": "string|null",
  "contacts": { "email":"string|null","phone":"string|null","location":"string|null","links":["string"] },
  "summary": "string|null",
  "skills": ["string"],
  "experience": [
    {"company":"string|null","role":"string|null","start":"YYYY-MM|null","end":"YYYY-MM|null","duration_months": "int|null","bullets":["string"]}
  ],
  "education": [
    {"degree":"string|null","school":"string|null","start":"YYYY-MM|null","end":"YYYY-MM|null"}
  ],
  "certs": ["string"],
  "total_duration_months": "int",
  "total_duration": "string",
  "__features": {
    "skills_norm": ["string"],
    "years_total": "number",
    "latest_role": "string|null",
    "latest_company": "string|null",
    "confidence": "number"
  }
}
```

---

## Demo Script (pitch 60 detik)

1. Upload CV.pdf → **profile JSON** tampil (nama, skills, pengalaman).
2. Sorot **duration\_months** dari “(4 Month)”, **total\_duration** otomatis.
3. Paste link lowongan → **ScamShield score** + alasan.
4. Klik “Tailor” → CV bullets & cover letter ATS-friendly.
5. “Open Gmail” → **draft** siap kirim (tanpa spam).

---
