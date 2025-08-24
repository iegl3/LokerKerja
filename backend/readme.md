# LokerKerja — Backend (CV Intelligence & Job Matching)

Backend untuk platform job matching yang:
1) menganalisis CV/portofolio,  
2) melakukan inferensi posisi kerja yang paling sesuai,  
3) menampilkan daftar lowongan relevan,  
4) mengirim newsletter lowongan terbaru yang cocok ke email pengguna (opt-in).

> Catatan: MVP **tidak** mengirim email ke HR/recruiter dan **bukan** mass-emailer. Fokus: analisis CV → inferensi role → job list → subscription + newsletter.

---

## Sponsor Mapping (komponen inti)

- **UNLI** — Vision & reasoning (OCR CV gambar/scan, bantuan reasoning untuk inferensi).
- **LUNOS** — Orchestration & structured parsing (normalisasi hasil analisis ke JSON; fallback/analytics).
- **MAILRY** — Email delivery & subscription (newsletter job alerts; unsubscribe webhook).

Ketiganya digunakan sebagai **bagian utama** alur backend.

---

## Fitur Utama

- **CV/Portfolio Parsing**
  - PDF searchable diproses langsung; PDF scan/gambar via OCR (UNLI).
  - Output JSON terstruktur (schema Pydantic), termasuk normalisasi tanggal dan durasi.

- **Job Position Inference**
  - Menentukan 1–3 posisi paling cocok beserta alasan singkat.

- **Job Discovery & Matching**
  - Integrasi agregator/scraper (JobSpy) untuk daftar lowongan relevan.

- **Subscription & Newsletter**
  - Endpoint subscribe/unsubscribe.
  - Scheduler background untuk mengirim email job alerts (Mailry).

- **Guardrails Ringan**
  - Validasi file & heuristik “probably CV”; respons 400 terstruktur jika input tak sesuai.

---

## Arsitektur Singkat

```text
Client/UI
   │
   ▼
FastAPI (src/api/main.py)
   ├─ CV Parser (UNLI OCR + Lunos parsing)
   ├─ Position Inference
   ├─ Job Search/Matching (JobSpy)
   ├─ Subscriptions (DB)
   └─ Mail Service (Mailry)
       └─ Scheduler background (job alerts)
```

<!-- separator -->

---

## Struktur Direktori (ringkas)

```text
.
├─ .env
├─ requirements.txt / pyproject.toml
├─ README.md
└─ src/
   ├─ cv_handler/                # paket parsing CV
   │  ├─ __init__.py
   │  ├─ schema.py               # Pydantic models
   │  ├─ reader.py               # pipeline utama (async)
   │  ├─ provider_lunos.py       # panggilan LUNOS
   │  ├─ provider_unli.py        # OCR & vision (UNLI)
   │  ├─ utils_*.py              # pdf/text/date/cache/log helpers
   ├─ jobs/                      # job discovery & matching
   │  ├─ jobspy_client.py        # wrapper JobSpy
   │  └─ matcher.py              # mapping skills → role → query
   ├─ integrations/
   │  ├─ mailry.py               # adaptor Mailry (send/list/webhook)
   │  └─ subscriptions.py        # CRUD subscription
   ├─ api/
   │  └─ main.py                 # FastAPI app & routes
   └─ scheduler.py               # background job alerts sender
```
