#!/usr/bin/env python3
"""Backfill / refresh media and migrate an existing issue JSON to schema v2 (west / east_asia).

Usage: python3 scripts/backfill.py --raw raw/media-backfill [--raw more_dirs] data/2026-10-20.json [...]

- Adds `media` to every post/reply whose attachments are found in the raw dumps
  (dumps must come from get_posts_by_ids with expansions=attachments.media_keys + media.fields).
- Marks `unavailable: true` on posts/replies that X reported as Not Found.
- Migrates region jp/kr -> east_asia + country JP/KR, re-ranks by heat, sets schema_version 2.
Text, metrics and translations are left untouched.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gtlib import build_index, media_for, normalize_region, rank_topics, REGIONS

ap = argparse.ArgumentParser(); ap.add_argument('--raw', action='append', required=True); ap.add_argument('files', nargs='+')
a = ap.parse_args()
posts, users, media, att, not_found = build_index(a.raw)
for f in a.files:
    d = json.load(open(f, encoding='utf-8'))
    stats = {"with_media_posts": 0, "with_media_replies": 0, "media_items": 0, "no_info": [], "unavailable": []}
    def apply(o, kind):
        m = media_for(o['id'], media, att)
        if m is None:
            if o['id'] not in not_found: stats['no_info'].append(o['id'])
        elif m:
            o['media'] = m; stats[f'with_media_{kind}'] += 1; stats['media_items'] += len(m)
        else:
            o.pop('media', None)
        if o['id'] in not_found:
            o['unavailable'] = True; stats['unavailable'].append(o['id'])
    for t in d['topics']:
        t['region'], c = normalize_region(t)
        if c: t['country'] = c
        for p in t['posts']:
            apply(p, 'posts')
            for r in p['replies']: apply(r, 'replies')
    rank_topics(d['topics'])
    d['schema_version'] = 2; d['regions'] = REGIONS
    json.dump(d, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"{f}: posts w/ media {stats['with_media_posts']}, replies w/ media {stats['with_media_replies']}, media items {stats['media_items']}, "
          f"no attachment info {len(stats['no_info'])} {stats['no_info'][:10]}, unavailable {stats['unavailable']}")
