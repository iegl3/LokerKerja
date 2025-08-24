import re
from datetime import datetime

MONTHS = {
    # EN
    "jan":1,"january":1,"feb":2,"february":2,"mar":3,"march":3,"apr":4,"april":4,"may":5,
    "jun":6,"june":6,"jul":7,"july":7,"aug":8,"august":8,"sep":9,"sept":9,"september":9,
    "oct":10,"october":10,"nov":11,"november":11,"dec":12,"december":12,
    # ID
    "januari":1,"februari":2,"maret":3,"april":4,"mei":5,"juni":6,"juli":7,"agustus":8,
    "september":9,"oktober":10,"november":11,"desember":12,
    "agt":8,"agu":8,"des":12,"okt":10,
}
PRESENT = {"now","present","current","ongoing","sekarang","kini","sd","s.d.","till now","to date"}

def _clean(s:str)->str:
    return re.sub(r"\s+"," ", s.strip().lower().replace("–","-").replace("—","-").replace("."," "))

def parse_date_any(s:str|None):
    if not s: return None
    x=_clean(str(s))
    m=re.search(r'\b(20\d{2}|19\d{2})[-/\.](0?[1-9]|1[0-2])\b',x)
    if m: return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}"
    m=re.search(r'\b(0?[1-9]|1[0-2])[-/\.](20\d{2}|19\d{2})\b',x)
    if m: return f"{int(m.group(2)):04d}-{int(m.group(1)):02d}"
    m=re.search(r'\b([a-z]+)\s+(20\d{2}|19\d{2})\b',x)
    if m and m.group(1) in MONTHS: return f"{int(m.group(2)):04d}-{MONTHS[m.group(1)]:02d}"
    m=re.search(r'\b(20\d{2}|19\d{2})\s+([a-z]+)\b',x)
    if m and m.group(2) in MONTHS: return f"{int(m.group(1)):04d}-{MONTHS[m.group(2)]:02d}"
    if any(p in x for p in PRESENT):
        y=int(datetime.now().strftime("%Y")); mo=int(datetime.now().strftime("%m")); return f"{y:04d}-{mo:02d}"
    m=re.search(r'\b(20\d{2}|19\d{2})\b',x)
    if m: return f"{int(m.group(1)):04d}-01"
    return None

def months_index(ym:str|None):
    if not ym: return None
    try: y=int(ym[:4]); m=int(ym[5:7]); return y*12+m
    except: return None

def humanize_months(total:int)->str:
    y,m=divmod(max(0,total),12)
    if y and m: return f"{y} tahun {m} bulan"
    if y: return f"{y} tahun"
    return f"{m} bulan"