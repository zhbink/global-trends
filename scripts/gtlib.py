"""Shared helpers for global-trends scripts (raw X dump parsing, media, regions)."""
import glob, json, os

REGIONS = [{"id": "west", "name_zh": "欧美"}, {"id": "east_asia", "name_zh": "日韩"}]
COUNTRY_NAMES = {"JP": "日本", "KR": "韩国"}
LEGACY_REGION = {"jp": ("east_asia", "JP"), "kr": ("east_asia", "KR")}
MAX_MP4_BITRATE = 2_500_000


def iter_json_objects(text):
    dec = json.JSONDecoder(); i = 0
    while True:
        cands = [x for x in (text.find('{"data"', i), text.find('{"meta"', i)) if x >= 0]
        if not cands: return
        j = min(cands)
        try:
            obj, end = dec.raw_decode(text[j:]); yield obj; i = j + end
        except Exception:
            i = j + 1


def raw_files(raw_dirs):
    for d in raw_dirs:
        for ext in ('txt', 'json'):
            yield from glob.glob(os.path.join(d, '**', f'*.{ext}'), recursive=True)


def build_index(raw_dirs):
    """Index posts, users, media and attachments from all raw X API dumps.
    Returns (posts, users, media, attachments, not_found).
    attachments[id] = media_keys (union over every response that included the field)."""
    if isinstance(raw_dirs, str): raw_dirs = [raw_dirs]
    posts, users, media, att, not_found = {}, {}, {}, {}, set()
    for f in raw_files(raw_dirs):
        try: text = open(f, encoding='utf-8').read()
        except Exception: continue
        for obj in iter_json_objects(text):
            inc = obj.get('includes') or {}
            for u in inc.get('users', []) or []: users[u['id']] = u
            for m in inc.get('media', []) or []:
                if m.get('media_key'): media[m['media_key']] = {**media.get(m['media_key'], {}), **m}
            for e in obj.get('errors', []) or []:
                if e.get('parameter') == 'ids' and e.get('resource_id'): not_found.add(e['resource_id'])
            data = obj.get('data')
            if isinstance(data, list):
                # A response counts as "media-aware" if it carries includes.media or any attachments field;
                # then posts in it without attachments are known to have no media.
                media_aware = bool(inc.get('media')) or any(isinstance(p, dict) and 'attachments' in p for p in data)
                for p in data:
                    if not isinstance(p, dict) or 'id' not in p: continue
                    keys = (p.get('attachments') or {}).get('media_keys')
                    if keys: att[p['id']] = list(dict.fromkeys(att.get(p['id'], []) + keys))
                    elif media_aware: att.setdefault(p['id'], [])
                    if 'public_metrics' in p and 'text' in p: posts[p['id']] = p
    return posts, users, media, att, not_found


def norm_media(m):
    """Convert one X media object into the site's compact media schema. Only real returned fields."""
    t = m.get('type')
    out = {"key": m.get('media_key'), "type": t}
    if t == 'photo':
        if not m.get('url'): return None
        out['url'] = m['url']
    else:
        if m.get('preview_image_url'): out['preview_url'] = m['preview_image_url']
        mp4s = [v for v in (m.get('variants') or []) if v.get('content_type') == 'video/mp4' and v.get('url')]
        if mp4s:
            ok = [v for v in mp4s if (v.get('bit_rate') or 0) <= MAX_MP4_BITRATE]
            pick = max(ok, key=lambda v: v.get('bit_rate') or 0) if ok else min(mp4s, key=lambda v: v.get('bit_rate') or 0)
            out['mp4'] = pick['url']
        if m.get('duration_ms') is not None: out['duration_ms'] = m['duration_ms']
        if not out.get('preview_url') and not out.get('mp4'): return None
    for k in ('width', 'height'):
        if isinstance(m.get(k), int): out[k] = m[k]
    if m.get('alt_text'): out['alt_text'] = m['alt_text']
    return out


def media_for(pid, media, att):
    """List of normalized media for a post id, or None if attachments were never fetched."""
    if pid not in att: return None
    res = []
    for k in att[pid]:
        if k in media:
            n = norm_media(media[k])
            if n: res.append(n)
    return res


def normalize_region(t):
    """Map legacy jp/kr regions to east_asia + country. Returns (region, country)."""
    r = t.get('region'); c = t.get('country')
    if r in LEGACY_REGION:
        r, c0 = LEGACY_REGION[r]; c = c or c0
    return r, c


def rank_topics(topics):
    """Rank inside each region by heat.post_count (desc); stable for ties."""
    counters = {}
    order = {r['id']: i for i, r in enumerate(REGIONS)}
    topics.sort(key=lambda t: (order.get(t['region'], 9), -(t.get('heat', {}).get('post_count') or 0)))
    for t in topics:
        counters[t['region']] = counters.get(t['region'], 0) + 1
        t['rank'] = counters[t['region']]
    return topics
