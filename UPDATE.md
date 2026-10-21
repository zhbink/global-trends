# 每日更新流程（global-trends）

每期 = `data/YYYY-MM-DD.json` 一个文件 + `data/index.json` 里的一条记录。站点是纯静态的，推送到 `main` 后 GitHub Pages 会自动生效。

> 铁律：**所有帖子、id、作者、数字、回复都必须来自 X 接口的原始返回**，不能手写或编造。取不到的就少列，并在 `note_zh` / `replies_note_zh` 里说明。

## 0. 目录约定

```
data/index.json              期目录（scripts/update_index.py 自动生成）
data/YYYY-MM-DD.json         每期数据（scripts/assemble.py 自动生成）
editorial/YYYY-MM-DD.py      编辑层：选题、选中的帖子/回复 id、中文标题/摘要/翻译/备注
editorial/YYYY-MM-DD.counts.json   每个话题的帖子数（get_posts_counts_recent 的 meta.total_tweet_count）
editorial/YYYY-MM-DD.queries.json  对应的计数查询语句
raw/YYYY-MM-DD/              X 接口原始返回（已 .gitignore，不入库）
scripts/gtlib.py             共用：解析原始返回、媒体规范化、地区映射、按热度排名
scripts/backfill.py          给已发布的期补抓/刷新媒体并迁移到 schema v2
```

## 1. 抓取策略（仅用 `x` MCP）

额度：每分钟 30 次、每天 1000 次。**每期预算 150–250 次**（首期实际 134 次，其中媒体补齐约 2–3 次）。统计窗口 = 抓取时刻往前 24 小时（UTC）。建议把每次调用都设 `write_to_file: true`，再把返回的文件复制到 `raw/YYYY-MM-DD/`。

| 步骤 | 工具 | 调用数 | 说明 |
|---|---|---|---|
| ① 趋势 | `get_trends_by_woeid` | 5 | woeid：美国 23424977、英国 23424975、日本 23424856、韩国 23424868、全球 1。**不要传 `trend.fields`**，会报错。 |
| ② 新闻聚类 | `search_news` | 10–20 | 用英/日/韩关键词或趋势词查询，带 `news.fields=...,cluster_posts_results`。每条新闻都会给出一组相关帖子 id，**这是找高赞帖子最有效的入口**。 |
| ③ 补充搜索 | `search_posts_all` | 20–40 | 用来查粉圈标签（如 `#HAPPY_K_DAY`）和官方账号（`from:xxx`）。注意 **`min_faves` 不被支持**；`sort_order=relevancy` 实际上也接近按时间排序，所以搜索结果主要用来“发现 id”，再统一批量拉取指标。加上 `-is:retweet` 和语言过滤 `lang:ja` / `lang:ko` / `lang:en`。 |
| ④ 批量拉指标 + 媒体 | `get_posts_by_ids` | 5–15 | 每次最多 100 个 id。参数名是 **`post.fields`**（不是 tweet.fields）：`post.fields=public_metrics,created_at,lang,conversation_id,author_id,attachments`、`expansions=author_id,attachments.media_keys`、`user.fields=username,name,public_metrics,verified`、`media.fields=media_key,type,url,preview_image_url,width,height,alt_text,variants,duration_ms`。转帖数字段可能叫 `repost_count` 或 `retweet_count`（assemble.py 已兼容）。按点赞数排序，选出每个话题 3–5 条。 |
| ⑤ 热度计数 | `get_posts_counts_recent` | 12–18 | 每个话题一次，`granularity=day`，取 `meta.total_tweet_count`，写进 `editorial/DATE.counts.json`，查询语句写进 `queries.json` 和 editorial 的 `query` 字段。 |
| ⑥ 热评 | `search_posts_all` | 50–110 | 搜索时同样带上 `expansions=author_id,attachments.media_keys` 和上面的 `media.fields`。每条入选帖子 1–2 次：`conversation_id:<帖子id> -from:<作者> -is:retweet`。**接口只返回最新的约 25 条**，所以对热门帖子再查一次“早期窗口”：`start_time` 设为帖子发布时间，`end_time` 设为发布后 15–90 分钟，这样能拿到早期、点赞更高的回复。两次结果合并去重后按点赞排序。不要按返回的 `conversation_id` 字段过滤，这个字段经常缺失。 |

| ⑦ 媒体补齐（**默认必做**） | `get_posts_by_ids` | 2–3 | 定稿后把编辑层里所有帖子 id 和回复 id（每期约 200 个）按 100 个一批，再拉一次步骤④的参数（主要是 attachments 和 media.fields），结果存进 `raw/DATE/`。这一步保证每条帖子和回复都有媒体信息，并能发现已删除的帖子（返回 Not Found 的会被标成 `unavailable`）。assemble 如果打印 `WARN: N posts/replies have no attachments info`，就说明这一步漏了。 |

媒体规则：图片只用接口返回的 `pbs.twimg.com` 原图 URL，前端会自动加 `?name=small` 或 `?name=large`。视频和 GIF 用 `preview_image_url` 做封面，`variants` 里选码率不超过 2.5Mbps 的最高一档 mp4 内嵌播放；如果没有 mp4，点击会跳转 X 原帖。所有媒体地址都必须是接口真实返回的，不得拼接或猜测。

过滤规则：去掉垃圾广告、成人内容、机器人或复制粘贴刷屏（粉圈应援模板、“Check DM”之类）、仇恨或歧视言论、未经证实的指控。被过滤的情况写进备注。

选题规则：分两个区域，**欧美（west）约 6–8 个，日韩（east_asia，日本和韩国合并）约 8–10 个**，总计 14–18 个。日韩话题要用 `country` 标注 `JP` 或 `KR`，日本和韩国大致均衡。每个区域内按热度（`heat.post_count`）从高到低自动排名，不再分日本、韩国小节。优先选择年轻人圈层的话题（追星、游戏/动漫、体育、网络梗、AI 与科技、生活方式、与年轻人相关的社会议题）。分类只能用：`娱乐/追星`、`游戏/动漫`、`体育`、`科技/AI`、`社会`、`生活方式`、`梗`。

## 2. 写编辑层 `editorial/DATE.py`

复制上一期的文件作为模板，填写这些字段：

```python
DATE = "2026-10-21"
WINDOW = {"start": "...Z", "end": "...Z"}
OBSERVATIONS = ["3–5 句今日观察"]
TRENDS = {"US": [...], "UK": [...], "JP": [...], "KR": [...], "WORLD": [...]}   # 来自步骤①
TOPICS = [{
  "key": "W1",                      # 对应 counts.json 的 key
  "id": "jp-xxx",                   # 唯一的 slug，前缀为 west- / jp- / kr-
  "region": "east_asia",            # west | east_asia（旧写法 jp / kr 会被自动映射）
  "country": "JP",                  # east_asia 必填：JP | KR；west 可省略
  "categories": ["体育"],
  "title_zh": "...", "summary_zh": "发生了什么", "why_youth_zh": "为什么年轻人在聊",
  "keywords": [...], "trend_hits": ["美国：..."], "query": "计数查询语句",
  "note_zh": "可选：数据局限说明",
  "posts": [{
    "id": "帖子 id",
    "text_zh": "译文（原文本身是中文时可以留空）",
    "note_zh": "可选",
    "replies": {"回复 id": "译文", ...},  # 3–5 条；原文是中文的写 ""
    "replies_note_zh": "可选：为什么少于 3 条"
  }]
}]
```

只写 id 和中文内容。原文、作者、时间、点赞/转发/回复/浏览数、链接都由 `assemble.py` 从 `raw/` 里自动填写。

## 3. 翻译规则

- 所有非中文的原文（英/日/韩/西班牙语等）都必须有 `text_zh`。校验脚本会报错拦截。
- 意译优先，读起来要像中文网友在说话；梗要保留含义，不要逐字直译。必要时用 `【译注：……】` 写一句简短说明，前端会单独显示成译注框。
- 人名、团名、作品名用中文圈的通行译法，例如 “文班”、“《赛博朋克：边缘行者》”，第一次出现时可以括注原文。
- 原文被接口截断（以 “…” 结尾）时，在译文末尾加 `【原文被截断】`。
- 回复开头的 `@用户名` 不用翻译。链接、标签可以省略。
- 不要美化，也不要删减观点。对冒犯性内容宁可整条不选。

## 4. 生成数据并校验

```bash
python3 scripts/assemble.py \
  --curated editorial/2026-10-21.py \
  --raw raw/2026-10-21 \          # 可重复传入多个 --raw 目录
  --counts editorial/2026-10-21.counts.json \
  --calls <本期 X 调用次数> \
  --out data/2026-10-21.json
python3 scripts/update_index.py      # 重建 data/index.json（按日期倒序，latest = 最新一期）
python3 scripts/validate.py          # 必须输出 OK: 0 errors
```

如果 assemble 报 `post/reply xxx not in raw cache`，说明这个 id 没有出现在任何原始返回里。要么补抓一次 `get_posts_by_ids`，要么从编辑层删掉它，**绝不手填**。

`validate.py` 检查以下内容：
- schema_version 为 2；west / east_asia 两个区域；east_asia 话题必须有 country（JP/KR）；区域内的 rank 为 1..n，并按热度降序；
- 媒体：type 只能是 photo / video / animated_gif；图片 url 必须是 pbs.twimg.com 原图；视频需要 preview_url 或 mp4，mp4 必须来自 video.twimg.com；宽、高、时长都是整数；
- schema 必填字段和类型；
- 地区和分类的取值；
- 每条非中文的帖子或回复都有中文译文；
- 链接格式为 `https://x.com/<username>/status/<id>`，并且 id 和用户名都与字段一致；
- 时间戳格式；
- `index.json` 与各期文件是否一致；
- 话题数和帖子数是否在目标范围内（超出范围只给 warning）。

### 给旧的期补媒体

```bash
# 把旧一期所有帖子和回复的 id 按 100 个一批，用 get_posts_by_ids 拉取（参数同步骤④），存到 raw/media-backfill-DATE/
python3 scripts/backfill.py --raw raw/media-backfill-DATE data/2026-10-20.json data/2026-10-21.json
python3 scripts/update_index.py && python3 scripts/validate.py
```

backfill 只会添加或刷新 `media` 和 `unavailable` 字段，同时把地区迁移到 v2；文本、数字和译文都保持不变。

## 5. 本地预览

```bash
python3 -m http.server 8000   # 打开 http://localhost:8000/#date=2026-10-21
```

## 6. 发布

```bash
git add data editorial && git commit -m "issue: 2026-10-21" && git push origin main
```

Pages（main 分支 / 根目录）大约 1 分钟后更新。验证命令：

```bash
curl -fsS https://zhbink.github.io/global-trends/data/index.json | head
```

## 7. 数据 schema（data/YYYY-MM-DD.json）

```jsonc
{
  "schema_version": 2, "date": "YYYY-MM-DD", "generated_at": "ISO8601Z",
  "window": {"start": "ISO8601Z", "end": "ISO8601Z"},
  "regions": [{"id": "west", "name_zh": "欧美"}, {"id": "east_asia", "name_zh": "日韩"}],
  "observations_zh": ["..."],
  "trends_snapshot": {"US": ["..."], ...},
  "topics": [{
    "id", "region": "west|east_asia", "country?": "JP|KR", "rank": "区域内按热度排名",
    "categories": [..], "title_zh", "summary_zh", "why_youth_zh",
    "keywords": [..], "trend_hits": [..], "note_zh?",
    "heat": {"post_count": int, "query": str, "window": {...}, "source": "x.get_posts_counts_recent"},
    "posts": [{
      "id", "url", "author": {"username", "name", "followers"}, "created_at", "lang",
      "text", "text_zh", "note_zh?", "replies_note_zh?", "unavailable?": true,
      "media?": [{"key", "type": "photo|video|animated_gif", "url?": "pbs 原图（photo）", "preview_url?": "pbs 封面（视频/GIF）",
                  "mp4?": "video.twimg.com mp4", "width?", "height?", "duration_ms?", "alt_text?"}],
      "metrics": {"likes", "reposts", "replies", "quotes", "views", "bookmarks"},
      "replies": [{"id", "url", "author": {"username", "name"}, "created_at", "lang", "text", "text_zh", "likes", "media?", "unavailable?"}]
    }]
  }],
  "meta": {"x_api_calls": int, "sources": [..], "limitations_zh": [..]}
}
```

`data/index.json`：`{"latest": "YYYY-MM-DD", "issues": [{"date", "topic_count", "post_count", "reply_count", "media_item_count", "regions": {"west": n, "east_asia": n}, "headline_zh"}]}`
