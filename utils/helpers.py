import re

__all__ = [
    "mca_clean_modid",
    "mca_levenshtein",
    "mca_normalize_modid",
]

# 用于提高性能的预编译正则模式
RE_CLEAN_INVALID = re.compile(r"[^A-Za-z0-9_.\-]")
RE_CLEAN_LEADING = re.compile(r"^[0-9\-_]+")
RE_HAS_ALPHA = re.compile(r"[A-Za-z]")

# 常用忽略词集合（使用字面量提高速度）
IGNORE_WORDS = {
    "mods.toml", "mods.toml file", "mods.tomlfile",
    "sound", "state", "unknown", "missing",
    "mod", "modfile", "mod file", "jar", "file", "or", "id"
}

def mca_clean_modid(raw: str):
    if not raw:
        return None
    # 使用预编译正则
    mid = RE_CLEAN_INVALID.sub("", raw).strip()
    if not mid:
        return None
    mid = RE_CLEAN_LEADING.sub("", mid)
    
    # 使用预编译正则搜索
    if not RE_HAS_ALPHA.search(mid):
        return None
        
    low = mid.lower()
    if low in IGNORE_WORDS or len(low) < 2:
        return None
    return mid

def mca_levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]

def mca_normalize_modid(name: str, mods_keys, mod_names):
    if not name:
        return None
    cand = name.strip()
    if cand in mods_keys:
        return cand
    low = cand.lower()
    for modid in mods_keys:
        if modid.lower() == low:
            return modid
    for modid, disp in (mod_names or {}).items():
        if disp and disp.lower() == low:
            return modid
    best = None
    best_score = 999
    for modid in mods_keys:
        dist = mca_levenshtein(low, modid.lower())
        if dist < best_score and dist <= 2:
            best_score = dist
            best = modid
    return best
