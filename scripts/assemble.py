#!/usr/bin/env python3
"""Assemble an issue JSON from (1) a curated editorial file and (2) raw X API dumps.

Why: every post/reply text, author, timestamp and metric comes straight from the raw
X API responses, so nothing numeric or quoted is typed by hand. The curated file only
holds editorial fields (titles, summaries, categories, translations, notes) plus the
post/reply ids to include.

Usage:
  python3 scripts/assemble.py --curated path/to/curated_YYYY-MM-DD.py \
      --raw /path/to/raw_dumps_dir --counts counts.json --calls 134 \
      --out data/YYYY-MM-DD.json

The raw dir may contain any number of files that hold X API JSON responses
(e.g. the files written by CallDynamicTool write_to_file). All objects of the
form {"data": [...], "includes": {"users": [...]}} are indexed.
counts.json maps topic key -> total post count from get_posts_counts_recent.
"""
import argparse, glob, html, json, os, re, runpy, sys, datetime as dt

def iter_json_objects(text):
    dec = json.JSONDecoder(); i = 0
    while True:
        j = text.find('{"data"', i)
        if j < 0:
            j2 = text.find('{"meta"', i)
            if j2 < 0: return
            j = j2
        try:
            obj, end = dec.raw_decode(text[j:]); yield obj; i = j + end
        except Exception:
            i = j + 1

def build_index(raw_dir):
    posts, users = {}, {}
    for f in glob.glob(os.path.join(raw_dir, '**', '*.txt'), recursive=True) + glob.glob(os.path.join(raw_dir, '**', '*.json'), recursive=True):
        try: text = open(f, encoding='utf-8').read()
        except Exception: continue
        for obj in iter_json_objects(text):
            for u in (obj.get('includes') or {}).get('users', []) or []:
                users[u['id']] = u
            data = obj.get('data')
            if isinstance(data, list):
                for p in data:
                    if isinstance(p, dict) and 'public_metrics' in p and 'text' in p:
                        posts[p['id']] = p
    return posts, users

def author(p, users):
    u = users.get(p.get('author_id'), {})
    un = u.get('username')
    if not un and p.get('url'):
        m = re.match(r'https://x\.com/([^/]+)/status/', p['url']); un = m.group(1) if m else None
    return {"username": un, "name": u.get('name'), "followers": (u.get('public_metrics') or {}).get('followers_count')}

def metrics(p):
    m = p['public_metrics']
    return {"likes": m.get('like_count', 0), "reposts": m.get('retweet_count', m.get('repost_count', 0)),
            "replies": m.get('reply_count', 0), "quotes": m.get('quote_count', 0),
            "views": m.get('impression_count'), "bookmarks": m.get('bookmark_count')}

CJK = re.compile(r'[\u4e00-\u9fff]'); KANA = re.compile(r'[\u3040-\u30ff]'); HANGUL = re.compile(r'[\uac00-\ud7af]')
def is_chinese(t):
    return bool(CJK.search(t)) and not KANA.search(t) and not HANGUL.search(t)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--curated', required=True); ap.add_argument('--raw', required=True)
    ap.add_argument('--counts', required=True); ap.add_argument('--calls', type=int, required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    C = runpy.run_path(a.curated); counts = json.load(open(a.counts))
    posts, users = build_index(a.raw)
    errors = []
    topics = []
    region_rank = {}
    for t in C['TOPICS']:
        region_rank[t['region']] = region_rank.get(t['region'], 0) + 1
        out_posts = []
        for cp in t['posts']:
            p = posts.get(cp['id'])
            if not p: errors.append(f"post {cp['id']} not in raw cache"); continue
            au = author(p, users); text = html.unescape(p['text'])
            reps = []
            for rid, rzh in cp.get('replies', {}).items():
                r = posts.get(rid)
                if not r: errors.append(f"reply {rid} not in raw cache"); continue
                ra = author(r, users); rtext = html.unescape(r['text'])
                if not rzh and is_chinese(rtext): rzh = rtext
                reps.append({"id": rid, "url": f"https://x.com/{ra['username']}/status/{rid}",
                             "author": {"username": ra['username'], "name": ra['name']},
                             "created_at": r.get('created_at'), "lang": r.get('lang'),
                             "text": rtext, "text_zh": rzh, "likes": r['public_metrics'].get('like_count', 0)})
            reps.sort(key=lambda r: -r['likes'])
            tzh = cp.get('text_zh') or (text if is_chinese(text) else '')
            op = {"id": cp['id'], "url": f"https://x.com/{au['username']}/status/{cp['id']}", "author": au,
                  "created_at": p.get('created_at'), "lang": p.get('lang'), "text": text, "text_zh": tzh,
                  "metrics": metrics(p), "replies": reps}
            if cp.get('note_zh'): op['note_zh'] = cp['note_zh']
            if cp.get('replies_note_zh'): op['replies_note_zh'] = cp['replies_note_zh']
            out_posts.append(op)
        out_posts.sort(key=lambda p: -p['metrics']['likes'])
        topic = {k: t[k] for k in ('id', 'region', 'categories', 'title_zh', 'summary_zh', 'why_youth_zh', 'keywords', 'trend_hits') if k in t}
        topic['rank'] = region_rank[t['region']]
        topic['heat'] = {"post_count": counts.get(t['key']), "query": t['query'],
                         "window": C['WINDOW'], "source": "x.get_posts_counts_recent"}
        if t.get('note_zh'): topic['note_zh'] = t['note_zh']
        topic['posts'] = out_posts
        topics.append(topic)
    issue = {
        "schema_version": 1,
        "date": C['DATE'],
        "generated_at": dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "window": C['WINDOW'],
        "regions": [{"id": "west", "name_zh": "欧美"}, {"id": "jp", "name_zh": "日本"}, {"id": "kr", "name_zh": "韩国"}],
        "observations_zh": C['OBSERVATIONS'],
        "trends_snapshot": C.get('TRENDS', {}),
        "topics": topics,
        "meta": {"x_api_calls": a.calls,
                 "sources": ["x.get_trends_by_woeid", "x.search_news", "x.search_posts_all", "x.get_posts_by_ids", "x.get_posts_counts_recent"],
                 "limitations_zh": [
                     "X 无法按年龄筛选用户，“年轻人”属性是根据话题、圈层与语言风格推断的。",
                     "热度为关键词/标签在统计窗口内的帖子数（get_posts_counts_recent），会混入无关帖与刷屏帖，只适合横向比较。",
                     "热门回复取自 X 搜索接口能返回的样本（主要是帖子发布初期与最近的回复），不保证是全部回复中点赞最高的。",
                     "部分长帖被 X 接口截断，原文以“…”结尾。所有译文为人工风格的意译，必要处附译注。"]}
    }
    if errors:
        print('\n'.join(errors), file=sys.stderr); sys.exit(1)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    json.dump(issue, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n_p = sum(len(t['posts']) for t in topics); n_r = sum(len(p['replies']) for t in topics for p in t['posts'])
    print(f"wrote {a.out}: {len(topics)} topics, {n_p} posts, {n_r} replies")

if __name__ == '__main__':
    main()
