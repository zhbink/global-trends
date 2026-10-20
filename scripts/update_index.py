#!/usr/bin/env python3
"""Rebuild data/index.json from all data/YYYY-MM-DD.json files (newest first)."""
import glob, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
issues = []
for f in glob.glob(os.path.join(ROOT, 'data', '*.json')):
    b = os.path.basename(f)
    if not re.match(r'^\d{4}-\d{2}-\d{2}\.json$', b): continue
    d = json.load(open(f, encoding='utf-8'))
    regions = {}
    for t in d['topics']: regions[t['region']] = regions.get(t['region'], 0) + 1
    issues.append({"date": d['date'], "topic_count": len(d['topics']),
                   "post_count": sum(len(t['posts']) for t in d['topics']),
                   "reply_count": sum(len(p['replies']) for t in d['topics'] for p in t['posts']),
                   "regions": regions, "headline_zh": d['topics'][0]['title_zh'] if d['topics'] else ''})
issues.sort(key=lambda i: i['date'], reverse=True)
idx = {"latest": issues[0]['date'] if issues else None, "issues": issues}
json.dump(idx, open(os.path.join(ROOT, 'data', 'index.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f"index.json: {len(issues)} issues, latest {idx['latest']}")
