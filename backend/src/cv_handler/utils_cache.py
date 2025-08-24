import json
from pathlib import Path
from datetime import datetime, timedelta

def load_cache(cache_dir:Path, key:str, ttl_days:int):
    meta_p=cache_dir/f"{key}.meta.json"; json_p=cache_dir/f"{key}.json"; txt_p=cache_dir/f"{key}.txt"
    if not json_p.exists() or not meta_p.exists(): return None
    try:
        meta=json.loads(meta_p.read_text(encoding="utf-8")); ts=meta.get("_ts")
        if ts and datetime.utcnow() - datetime.fromisoformat(ts) > timedelta(days=ttl_days): return None
        prof=json.loads(json_p.read_text(encoding="utf-8"))
        text=txt_p.read_text(encoding="utf-8") if txt_p.exists() else ""
        return prof, meta, text
    except: return None

def save_cache(cache_dir:Path, key:str, prof:dict, meta:dict, text:str):
    cache_dir.mkdir(exist_ok=True)
    meta2={**meta, "_ts": datetime.utcnow().isoformat(timespec="seconds")}
    (cache_dir/f"{key}.json").write_text(json.dumps(prof,ensure_ascii=False), encoding="utf-8")
    (cache_dir/f"{key}.meta.json").write_text(json.dumps(meta2,ensure_ascii=False), encoding="utf-8")
    if text: (cache_dir/f"{key}.txt").write_text(text, encoding="utf-8")