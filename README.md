# LokerKerja — CV Intelligence & Job Matching

Platform job matching yang menganalisis CV/portofolio untuk mengidentifikasi keahlian utama pengguna, melakukan **inferensi otomatis posisi kerja** yang paling cocok, lalu menampilkan **daftar lowongan relevan**. Pengguna dapat **berlangganan newsletter** agar menerima update lowongan terbaru yang sesuai profil melalui email.

> Catatan: MVP ini **tidak** melakukan pengiriman email massal atau auto-draft ke HR. Fokus: analisis CV → inferensi role → rekomendasi lowongan → newsletter.

---

## Latar Belakang & Masalah
- Banyak pencari kerja kesulitan menilai **posisi apa yang paling cocok** dari CV mereka.
- Informasi lowongan **tersebar** dan sering tidak relevan dengan keterampilan yang dimiliki.
- Dibutuhkan cara **cepat dan aman** untuk mendapatkan rekomendasi lowongan yang benar-benar sesuai.

---

## Solusi Singkat
1. **Analisis CV/Portofolio**  
   CV diproses untuk mengekstrak skill, pengalaman, dan kata kunci penting.
2. **Inferensi Posisi**  
   Sistem menyarankan 1–3 **role** yang paling sesuai beserta alasan singkat.
3. **Job Matching**  
   Menampilkan daftar lowongan relevan berdasarkan hasil analisis.
4. **Newsletter**  
   Pengguna dapat subscribe untuk menerima update lowongan terbaru yang cocok via email.

---

## Relevansi dengan Tema Hackathon
**AI Agent for Kemerdekaan Indonesia**: membantu pencari kerja “merdeka” dari lamaran tidak tepat sasaran dan informasi yang berserakan, melalui agen AI yang **memahami CV**, **menentukan role realistis**, dan **mengirim info peluang baru** secara berkala.

---

## Komponen Sponsor (Komponen Inti)
- **UNLI** — Vision & Reasoning  
  Mengolah CV berbasis gambar/PDF (OCR/vision) dan membantu inferensi posisi.
- **LUNOS** — Orkestrasi & Parsing Terstruktur  
  Menormalkan hasil analisis ke JSON standar serta mengelola pipeline AI.
- **MAILRY** — Email Newsletter  
  Mengirimkan update lowongan terbaru ke email pengguna serta unsubscribe.

> Ketiganya digunakan sebagai **bagian utama** alur sistem, bukan sekadar figuran.

---

## Alur Pengguna
1. Upload CV/portofolio.  
2. Lihat hasil analisis: skill utama + rekomendasi posisi.  
3. Terima daftar lowongan yang relevan.  
4. Subscribe untuk menerima update lowongan terbaru via email.

---

## Demo Yang Ditunjukkan (1–2 menit)
- Upload CV → hasil analisis & role yang disarankan.  
- Tampilkan lowongan relevan.  
- Subscribe newsletter → contoh email update masuk.

---

## Privasi & Kepatuhan (Ringkas)
- **Consent** eksplisit saat upload CV dan berlangganan email.  
- **Minimasi data**: hanya menyimpan data terstruktur seperlunya.  
- **Unsubscribe** satu klik melalui token unik.  
- Tidak ada pengiriman email massal ke HR.

---

## Roadmap Kedepannya
- Peringkat job lebih baik (ranking berbasis sinyal interaksi).
- Mode tailoring CV/cover letter (ATS-friendly).
- Peningkatan verifikasi lowongan dan guardrails konten untuk menghindari loker scam.
- Scraping info loker yang lebih luas dan valid
---

## Tim
LokerKerja — AI Agent Hackathon 2025  
Mapping sponsor: **UNLI (Vision/Reasoning)**, **LUNOS (Orchestration/Parsing)**, **MAILRY (Newsletter)**.
