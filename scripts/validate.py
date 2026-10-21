#!/usr/bin/env python3
"""Validate global-trends data files.

Usage: python3 scripts/validate.py            # validate data/index.json and every issue it lists
       python3 scripts/validate.py data/2026-10-20.json   # validate specific issue file(s)
Exit code 0 = OK, 1 = errors found. Warnings do not fail.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS = {"west", "east_asia"}
COUNTRIES = {"JP", "KR"}
REGION_TARGET = {"west": (6, 8), "east_asia": (8, 10)}
MEDIA_TYPES = {"photo", "video", "animated_gif"}
PBS_RE = re.compile(r'^https://pbs\.twimg\.com/[\w/.\-]+\.(jpg|jpeg|png|webp|gif)$')
MP4_RE = re.compile(r'^https://video\.twimg\.com/\S+\.mp4(\?\S*)?$')
CATEGORIES = {"娱乐/追星", "游戏/动漫", "体育", "科技/AI", "社会", "生活方式", "梗"}
URL_RE = re.compile(r'^https://x\.com/[A-Za-z0-9_]{1,15}/status/(\d+)$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
TS_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$')
CJK = re.compile(r'[\u4e00-\u9fff]'); KANA = re.compile(r'[\u3040-\u30ff]'); HANGUL = re.compile(r'[\uac00-\ud7af]')
STRIP = re.compile(r'https?://\S+|@\w+|#\S+')

def needs_translation(text):
    core = STRIP.sub('', text)
    if not re.search(r'[A-Za-z\u3040-\u30ff\uac00-\ud7af\u4e00-\u9fff\u00c0-\u024f\u0400-\u04ff\u0e00-\u0e7f]', core):
        return False  # emoji / links / hashtags only
    is_zh = bool(CJK.search(core)) and not KANA.search(core) and not HANGUL.search(core) and not re.search(r'[A-Za-z]{4,}', core)
    return not is_zh

class V:
    def __init__(s): s.errors = []; s.warnings = []
    def err(s, m): s.errors.append(m)
    def warn(s, m): s.warnings.append(m)

def req(v, obj, key, typ, where):
    if key not in obj: v.err(f"{where}: missing '{key}'"); return None
    if typ and not isinstance(obj[key], typ): v.err(f"{where}: '{key}' should be {typ}"); return None
    return obj[key]

def check_text(v, o, where):
    t = req(v, o, 'text', str, where); tz = o.get('text_zh')
    if t is None: return
    if needs_translation(t) and not (isinstance(tz, str) and tz.strip()):
        v.err(f"{where}: non-Chinese text without text_zh")
    if isinstance(tz, str) and tz.strip() and not CJK.search(tz):
        v.warn(f"{where}: text_zh contains no Chinese characters")

def check_url(v, o, where):
    u = req(v, o, 'url', str, where)
    if u is None: return
    m = URL_RE.match(u)
    if not m: v.err(f"{where}: bad url {u}")
    elif m.group(1) != o.get('id'): v.err(f"{where}: url id != id")
    un = (o.get('author') or {}).get('username')
    if m and un and f"/{un}/" not in u: v.err(f"{where}: url username mismatch")

def check_media(v, o, where):
    if 'media' not in o: return
    ms = o['media']
    if not isinstance(ms, list) or not ms: v.err(f"{where}: media must be a non-empty list when present"); return
    for i, m in enumerate(ms):
        mw = f"{where}.media[{i}]"
        if not isinstance(m, dict): v.err(f"{mw}: not an object"); continue
        t = m.get('type')
        if t not in MEDIA_TYPES: v.err(f"{mw}: bad type {t}"); continue
        if not m.get('key'): v.err(f"{mw}: key missing")
        if t == 'photo':
            if not PBS_RE.match(str(m.get('url', ''))): v.err(f"{mw}: photo url must be pbs.twimg.com original: {m.get('url')}")
        else:
            if not m.get('preview_url') and not m.get('mp4'): v.err(f"{mw}: video/gif needs preview_url or mp4")
            if m.get('preview_url') and not PBS_RE.match(m['preview_url']): v.err(f"{mw}: bad preview_url {m['preview_url']}")
            if m.get('mp4') and not MP4_RE.match(m['mp4']): v.err(f"{mw}: bad mp4 url {m['mp4']}")
        for k in ('width', 'height', 'duration_ms'):
            if k in m and not isinstance(m[k], int): v.err(f"{mw}: {k} must be int")

def validate_issue(path, v):
    try: d = json.load(open(path, encoding='utf-8'))
    except Exception as e: v.err(f"{path}: cannot parse JSON: {e}"); return None
    w = os.path.basename(path)
    date = req(v, d, 'date', str, w)
    if date and not DATE_RE.match(date): v.err(f"{w}: bad date")
    if date and not w.startswith(date): v.err(f"{w}: filename does not match date")
    for k in ('window',):
        win = req(v, d, k, dict, w)
        if win:
            for kk in ('start', 'end'):
                if not TS_RE.match(str(win.get(kk, ''))): v.err(f"{w}: window.{kk} bad timestamp")
    obs = req(v, d, 'observations_zh', list, w)
    if obs is not None and not (3 <= len(obs) <= 5): v.warn(f"{w}: observations_zh should have 3-5 items (has {len(obs)})")
    topics = req(v, d, 'topics', list, w) or []
    if not (14 <= len(topics) <= 18): v.warn(f"{w}: {len(topics)} topics (target 14-18)")
    per_region = {}
    ids = set(); post_ids = set()
    for i, t in enumerate(topics):
        tw = f"{w}:topic[{i}]"
        tid = req(v, t, 'id', str, tw)
        if tid in ids: v.err(f"{tw}: duplicate topic id")
        ids.add(tid)
        r = req(v, t, 'region', str, tw)
        if r and r not in REGIONS: v.err(f"{tw}: region '{r}' not in {REGIONS}")
        per_region[r] = per_region.get(r, 0) + 1
        if r == 'east_asia' and t.get('country') not in COUNTRIES: v.err(f"{tw}: east_asia topic needs country in {COUNTRIES}")
        if 'rank' in t and not isinstance(t['rank'], int): v.err(f"{tw}: rank must be int")
        for k in ('title_zh', 'summary_zh', 'why_youth_zh'):
            s = req(v, t, k, str, tw)
            if s is not None and not CJK.search(s): v.err(f"{tw}: {k} must be Chinese")
        cats = req(v, t, 'categories', list, tw) or []
        if not cats: v.err(f"{tw}: categories empty")
        for c in cats:
            if c not in CATEGORIES: v.err(f"{tw}: unknown category '{c}'")
        req(v, t, 'keywords', list, tw)
        heat = req(v, t, 'heat', dict, tw)
        if heat is not None:
            pc = heat.get('post_count')
            if not isinstance(pc, int) or pc < 0: v.err(f"{tw}: heat.post_count must be non-negative int")
            if not heat.get('query'): v.err(f"{tw}: heat.query missing")
        posts = req(v, t, 'posts', list, tw) or []
        if not (1 <= len(posts)): v.err(f"{tw}: no posts")
        if len(posts) < 3: v.warn(f"{tw}: only {len(posts)} posts (target 3-5)")
        for j, p in enumerate(posts):
            pw = f"{tw}.posts[{j}]"
            pid = req(v, p, 'id', str, pw)
            if pid and not pid.isdigit(): v.err(f"{pw}: id not numeric")
            if pid in post_ids: v.warn(f"{pw}: post {pid} appears in multiple topics")
            post_ids.add(pid)
            a = req(v, p, 'author', dict, pw)
            if a is not None and not a.get('username'): v.err(f"{pw}: author.username missing")
            check_url(v, p, pw); check_text(v, p, pw); check_media(v, p, pw)
            ts = req(v, p, 'created_at', str, pw)
            if ts and not TS_RE.match(ts): v.err(f"{pw}: bad created_at")
            m = req(v, p, 'metrics', dict, pw)
            if m is not None:
                for k in ('likes', 'reposts', 'replies'):
                    if not isinstance(m.get(k), int): v.err(f"{pw}: metrics.{k} must be int")
            reps = req(v, p, 'replies', list, pw)
            if reps is not None and len(reps) == 0 and not p.get('replies_note_zh'):
                v.warn(f"{pw}: no replies and no replies_note_zh")
            for k, rp in enumerate(reps or []):
                rw = f"{pw}.replies[{k}]"
                req(v, rp, 'id', str, rw); check_url(v, rp, rw); check_text(v, rp, rw); check_media(v, rp, rw)
                if not isinstance(rp.get('likes'), int): v.err(f"{rw}: likes must be int")
    for r, (lo, hi) in REGION_TARGET.items():
        n = per_region.get(r, 0)
        if not (lo <= n <= hi): v.warn(f"{w}: region {r} has {n} topics (target {lo}-{hi})")
    if d.get('schema_version') != 2: v.err(f"{w}: schema_version must be 2")
    ranks = {}
    for t in topics: ranks.setdefault(t.get('region'), []).append(t.get('rank'))
    for r, rs in ranks.items():
        if rs != list(range(1, len(rs) + 1)): v.err(f"{w}: ranks in {r} must be 1..n in file order")
        hs = [t['heat']['post_count'] for t in topics if t.get('region') == r and isinstance(t.get('heat'), dict)]
        if hs != sorted(hs, reverse=True): v.warn(f"{w}: {r} topics not sorted by heat")
    req(v, d, 'meta', dict, w)
    return d

def main():
    v = V()
    files = sys.argv[1:]
    if not files:
        idx_path = os.path.join(ROOT, 'data', 'index.json')
        try: idx = json.load(open(idx_path, encoding='utf-8'))
        except Exception as e: print(f"ERROR index.json: {e}"); sys.exit(1)
        issues = idx.get('issues')
        if not isinstance(issues, list) or not issues: v.err('index.json: issues must be non-empty list')
        dates = [i.get('date') for i in issues or []]
        if dates != sorted(dates, reverse=True): v.err('index.json: issues must be sorted newest first')
        if idx.get('latest') != (dates[0] if dates else None): v.err('index.json: latest != first issue date')
        for it in issues or []:
            f = os.path.join(ROOT, 'data', f"{it.get('date')}.json")
            if not os.path.exists(f): v.err(f"index.json: missing file for {it.get('date')}"); continue
            d = validate_issue(f, v)
            if d and it.get('topic_count') != len(d.get('topics', [])): v.err(f"index.json: topic_count mismatch for {it.get('date')}")
    else:
        for f in files: validate_issue(f, v)
    for wmsg in v.warnings: print('WARN ', wmsg)
    for e in v.errors: print('ERROR', e)
    print(f"{'FAILED' if v.errors else 'OK'}: {len(v.errors)} errors, {len(v.warnings)} warnings")
    sys.exit(1 if v.errors else 0)

if __name__ == '__main__':
    main()
