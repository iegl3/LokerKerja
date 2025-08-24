# src/cv_handler/reader.py
import os, re, json, time, asyncio, tempfile
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from pydantic import ValidationError

# internal imports (pakai absolute package path)
from cv_handler.schema import Profile
from cv_handler.logutil import jlog
from cv_handler.utils_io import sha256_file, b64_image_bytes, guess_mime
from cv_handler.utils_pdf import pdf_extract_text, pdf_page_to_png_bytes
from cv_handler.utils_cache import load_cache, save_cache
from cv_handler.utils_dates import parse_date_any, months_index, humanize_months
from cv_handler.provider_unli import unli_vision_ocr_async
from cv_handler.provider_lunos import lunos_parse_async, lunos_fill_dates_async

# =========================
# Heuristik durasi
# =========================
DUR_PAT = re.compile(r'(\d{1,2})\s*(bulan|bln|month|months|mo|mos)', re.I)

# =========================
# Normalisasi & Validasi
# =========================
def normalize_profile(p: dict) -> dict:
    """Rapikan struktur JSON hasil LLM: skills dedup, tanggal ke 'YYYY-MM',
    pindahkan '4 months' dari start/end ke duration_months, dll."""
    p = p or {}
    p["skills"] = list(dict.fromkeys([s.strip() for s in (p.get("skills") or []) if s]))[:30]

    for e in p.get("experience", []) or []:
        # Pindahkan durasi yang salah taruh di start/end
        for k in ("start", "end"):
            v = e.get(k)
            if isinstance(v, str) and DUR_PAT.search(v or ""):
                try:
                    dm = int(DUR_PAT.search(v).group(1))
                    if 0 < dm <= 72:
                        e["duration_months"] = dm
                except Exception:
                    pass
                e[k] = None

        # Pecah pola "Apr 2024 - Now" yg nyangkut di start
        s = e.get("start")
        if isinstance(s, str) and ("-" in s) and (e.get("end") in (None, "")):
            m = re.search(r'(.+?)\s*[-–—]\s*(.+)', s)
            if m:
                e["start"] = parse_date_any(m.group(1))
                e["end"]   = parse_date_any(m.group(2))

        # Normalize tanggal (EN/ID)
        e["start"] = parse_date_any(e.get("start"))
        e["end"]   = parse_date_any(e.get("end"))

        # Bullets & clamp durasi
        e["bullets"] = [re.sub(r"\s+", " ", x).strip() for x in (e.get("bullets") or []) if x][:6]
        if e.get("duration_months") is not None:
            try:
                dm = int(e["duration_months"])
                e["duration_months"] = dm if 0 < dm <= 72 else None
            except Exception:
                e["duration_months"] = None

    for ed in p.get("education", []) or []:
        ed["start"] = parse_date_any(ed.get("start")) or None
        ed["end"]   = parse_date_any(ed.get("end")) or None

    c = p.get("contacts") or {}
    if c.get("phone"):
        ph = str(c["phone"])
        c["phone_masked"] = ph[:-4] + "****" if len(ph) > 4 else "****"
    p["contacts"] = c
    return p


def validate_profile(p: dict) -> dict:
    """Validasi ke schema Pydantic; harden bila ada noise."""
    try:
        return Profile.model_validate(p).model_dump()
    except ValidationError:
        allow = {
            "schema_version", "source", "name", "contacts", "summary", "skills",
            "experience", "education", "certs", "extras",
            "total_duration_months", "total_duration"
        }
        base = {k: v for k, v in p.items() if k in allow}
        base.setdefault("contacts", {})
        base.setdefault("skills", [])
        base.setdefault("experience", [])
        base.setdefault("education", [])
        base.setdefault("certs", [])
        base.setdefault("extras", {})
        base.setdefault("total_duration_months", 0)
        base.setdefault("total_duration", None)
        return base


def enrich_duration_from_text(profile: dict, cv_text: str) -> dict:
    """Isi duration_months jika kosong menggunakan regex di sekitar company/role; fallback global urut."""
    text_low = cv_text.lower()
    unmatched = []

    for e in profile.get("experience", []) or []:
        if e.get("duration_months") is None:
            dur = None
            for cue in (e.get("company"), e.get("role")):
                if cue:
                    i = text_low.find(str(cue).lower())
                    if i != -1:
                        window = cv_text[max(0, i - 120): i + 200]
                        m = DUR_PAT.search(window)
                        if m:
                            try:
                                v = int(m.group(1))
                                dur = v if 0 < v <= 72 else None
                            except Exception:
                                pass
                            if dur:
                                break
            if dur is not None:
                e["duration_months"] = dur
            else:
                unmatched.append(e)

    if unmatched:
        all_durs = []
        for m in DUR_PAT.finditer(cv_text):
            try:
                v = int(m.group(1))
                if 0 < v <= 72:
                    all_durs.append(v)
            except Exception:
                ...
        if len(all_durs) >= len(unmatched):
            for e, d in zip(unmatched, all_durs[:len(unmatched)]):
                if e.get("duration_months") is None:
                    e["duration_months"] = d
    return profile


def compute_total_duration_months(p: dict) -> int:
    """Akumulasi total durasi pengalaman dari start/end (atau duration_months)."""
    total = 0
    now_idx = months_index(time.strftime("%Y-%m"))

    for e in p.get("experience", []) or []:
        m1 = months_index(e.get("start"))
        m2 = months_index(e.get("end")) or now_idx  # role aktif → kini
        if m1 and m2 and m2 >= m1:
            total += (m2 - m1)
        else:
            try:
                dm = int(e.get("duration_months")) if e.get("duration_months") is not None else None
            except Exception:
                dm = None
            if dm:
                total += dm
    return total


def derive_features(p: dict) -> dict:
    """Fitur turunan ringan untuk downstream scoring/matching."""
    skills = set([s.lower() for s in p.get("skills") or []])
    latest_role = latest_company = None
    if p.get("experience"):
        latest_role = p["experience"][0].get("role")
        latest_company = p["experience"][0].get("company")
    conf = round((bool(p.get("name")) + (len(skills) >= 5) + (len(p.get("experience") or []) > 0)) / 3, 2)
    return {
        "skills_norm": sorted(skills)[:30],
        "latest_role": latest_role,
        "latest_company": latest_company,
        "confidence": conf
    }

# =========================
# Core Pipeline (async)
# =========================
async def read_cv_async(
    path: Path,
    pages_spec: Optional[str],
    force_ocr: bool,
    max_pages: int,
    scale: float,
    cache: bool,
    ttl_days: int,
    req_id: str
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, bool]]:
    """Pipeline utama: PDF/image → (OCR jika perlu) → LLM parse → normalisasi → enrich → total durasi."""
    t_all = time.perf_counter()
    meta = {
        "ocr_ms": "0.0 ms", "ocr_model": "-",
        "parse_ms": "-", "parse_model": "-",
        "fix_ms": "-", "fix_model": "-",
        "total_ms": None
    }
    cache_dir = Path.cwd() / ".cache"
    key = f"{sha256_file(path)}-{pages_spec or 'auto'}-{int(force_ocr)}-{max_pages}-{scale}"

    # Cache
    if cache:
        loaded = load_cache(cache_dir, key, ttl_days)
        if loaded:
            prof, meta_cached, _text = loaded
            meta = {**meta_cached, "total_ms": f"{(time.perf_counter()-t_all)*1000:.1f} ms"}
            jlog(event="cache_hit", req_id=req_id, key=key)
            return prof, meta, {"from_cache": True}

    # Ekstraksi teks cepat
    ext = path.suffix.lower()
    text = ""
    if ext == ".pdf" and not force_ocr:
        text = await asyncio.to_thread(pdf_extract_text, path)

    # OCR (gambar/scan/teks pendek)
    if (ext in {".png", ".jpg", ".jpeg", ".webp"}) or force_ocr or (ext == ".pdf" and len(text) < 500):
        imgs = []
        if ext == ".pdf":
            # Resolve pages
            if pages_spec:
                pages = []
                for part in pages_spec.split(","):
                    if "-" in part:
                        a, b = part.split("-")
                        pages += list(range(int(a), int(b) + 1))
                    else:
                        pages.append(int(part))
            else:
                pages = list(range(1, max_pages + 1))
            pages = pages[:max_pages]

            # Render & autoscale bila >6MB
            t_render = time.perf_counter()
            for p in pages:
                bb = await asyncio.to_thread(pdf_page_to_png_bytes, path, p - 1, scale)
                cur = scale
                while len(bb) > 6_000_000 and cur > 0.8:
                    cur = round(cur * 0.8, 2)
                    bb = await asyncio.to_thread(pdf_page_to_png_bytes, path, p - 1, cur)
                imgs.append(b64_image_bytes(bb, "image/png"))
            render_ms = f"{(time.perf_counter()-t_render)*1000:.1f} ms"
        else:
            imgs = [b64_image_bytes(open(path, "rb").read(), guess_mime(path))]
            render_ms = "0.0 ms"

        text, ocr_ms, ocr_model = await unli_vision_ocr_async(imgs, req_id)
        meta["ocr_ms"] = f"{ocr_ms} (+render {render_ms})"
        meta["ocr_model"] = ocr_model
    else:
        meta["ocr_ms"] = "0.0 ms"
        meta["ocr_model"] = "-"

    # LLM parse → normalize → validate
    parsed, meta["parse_ms"], meta["parse_model"] = await lunos_parse_async(
        text or await asyncio.to_thread(pdf_extract_text, path), req_id
    )
    norm = normalize_profile(parsed)
    valid = validate_profile(norm)

    # Enrich duration dari teks (tanpa nebak tanggal)
    valid = enrich_duration_from_text(valid, text or "")

    # Optional: isi tanggal kalau ada bukti eksplisit di teks
    fixed, meta["fix_ms"], meta["fix_model"] = await lunos_fill_dates_async(text or "", valid, req_id)
    prof = validate_profile(fixed)

    # Total durasi akumulatif + fitur
    total_months = compute_total_duration_months(prof)
    prof["total_duration_months"] = total_months
    prof["total_duration"] = humanize_months(total_months)

    feats = derive_features(prof)
    feats["years_total"] = round(total_months / 12, 1)  # sinkron
    prof["__features"] = feats

    # Final meta + cache
    meta["total_ms"] = f"{(time.perf_counter()-t_all)*1000:.1f} ms"
    save_cache(cache_dir, key, prof, meta, text) if cache else None

    return prof, meta, {"from_cache": False}


# =========================
# Web-friendly: bytes input
# =========================
async def read_cv_from_bytes_async(
    data: bytes,
    filename: str = "upload.pdf",
    pages: Optional[str] = None,
    force_ocr: bool = False,
    max_pages: int = 3,
    scale: float = 2.0,
    use_cache: bool = True,
    ttl_days: int = 7,
    req_id: str = "web",
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, bool]]:
    """Terima file sebagai bytes (mis. dari UploadFile FastAPI), proses, lalu hapus file temp."""
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(prefix="cv_", suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return await read_cv_async(
            tmp_path, pages, force_ocr, max_pages, scale,
            cache=use_cache, ttl_days=ttl_days, req_id=req_id
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass