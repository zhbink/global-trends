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
```

## 1. 抓取策略（仅用 `x` MCP）

额度：每分钟 30 次、每天 1000 次。**每期预算 150–250 次**（首期实际 134 次）。统计窗口 = 抓取时刻往前 24 小时（UTC）。建议把每次调用都设 `write_to_file: true`，再把返回的文件复制到 `raw/YYYY-MM-DD/`。

| 步骤 | 工具 | 调用数 | 说明 |
|---|---|---|---|
| ① 趋势 | `get_trends_by_woeid` | 5 | woeid：美国 23424977、英国 23424975、日本 23424856、韩国 23424868、全球 1。**不要传 `trend.fields`**，会报错。 |
| ② 新闻聚类 | `search_news` | 10–20 | 用英/日/韩关键词或趋势词查询，带 `news.fields=...,cluster_posts_results`。每条新闻都会给出一组相关帖子 id，**这是找高赞帖子最有效的入口**。 |
| ③ 补充搜索 | `search_posts_all` | 20–40 | 用来查粉圈标签（如 `#HAPPY_K_DAY`）和官方账号（`from:xxx`）。注意 **`min_faves` 不被支持**；`sort_order=relevancy` 实际上也接近按时间排序，所以搜索结果主要用来“发现 id”，再统一批量拉取指标。加上 `-is:retweet` 和语言过滤 `lang:ja` / `lang:ko` / `lang:en`。 |
| ④ 批量拉指标 | `get_posts_by_ids` | 5–15 | 每次最多 100 个 id，带 `tweet.fields=public_metrics,created_at,lang,conversation_id,author_id`、`expansions=author_id`、`user.fields=username,name,public_metrics,verified`。转帖数字段可能叫 `repost_count` 或 `retweet_count`（assemble.py 已兼容）。按点赞数排序，选出每个话题 3–5 条。 |
| ⑤ 热度计数 | `get_posts_counts_recent` | 12–18 | 每个话题一次，`granularity=day`，取 `meta.total_tweet_count`，写进 `editorial/DATE.counts.json`，查询语句写进 `queries.json` 和 editorial 的 `query` 字段。 |
| ⑥ 热评 | `search_posts_all` | 50–110 | 每条入选帖子 1–2 次：`conversation_id:<帖子id> -from:<作者> -is:retweet`。**接口只返回最新的约 25 条**，所以对热门帖子再查一次“早期窗口”：`start_time` 设为帖子发布时间，`end_time` 设为发布后 15–90 分钟，这样能拿到早期、点赞更高的回复。两次结果合并去重后按点赞排序。不要按返回的 `conversation_id` 字段过滤，这个字段经常缺失。 |

过滤规则：去掉垃圾广告、成人内容、机器人或复制粘贴刷屏（粉圈应援模板、“Check DM”之类）、仇恨或歧视言论、未经证实的指控。被过滤的情况写进备注。

选题规则：欧美、日本、韩国各 4–6 个话题（总计 12–18 个）。优先选择年轻人圈层的话题（追星、游戏/动漫、体育、网络梗、AI 与科技、生活方式、与年轻人相关的社会议题）。分类只能用：`娱乐/追星`、`游戏/动漫`、`体育`、`科技/AI`、`社会`、`生活方式`、`梗`。

## 2. 写编辑层 `editorial/DATE.py`

复制上一期的文件作为模板，填写这些字段：

```python
DATE = "2026-10-21"
WINDOW = {"start": "...Z", "end": "...Z"}
OBSERVATIONS = ["3–5 句今日观察"]
TRENDS = {"US": [...], "UK": [...], "JP": [...], "KR": [...], "WORLD": [...]}   # 来自步骤①
TOPICS = [{
  "key": "W1",                      # 对应 counts.json 的 key
  "id": "west-xxx",                 # 唯一的 slug，前缀为 west- / jp- / kr-
  "region": "west",                 # west | jp | kr
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
  --raw raw/2026-10-21 \
  --counts editorial/2026-10-21.counts.json \
  --calls <本期 X 调用次数> \
  --out data/2026-10-21.json
python3 scripts/update_index.py      # 重建 data/index.json（按日期倒序，latest = 最新一期）
python3 scripts/validate.py          # 必须输出 OK: 0 errors
```

如果 assemble 报 `post/reply xxx not in raw cache`，说明这个 id 没有出现在任何原始返回里。要么补抓一次 `get_posts_by_ids`，要么从编辑层删掉它，**绝不手填**。

`validate.py` 检查以下内容：
- schema 必填字段和类型；
- 地区和分类的取值；
- 每条非中文的帖子或回复都有中文译文；
- 链接格式为 `https://x.com/<username>/status/<id>`，并且 id 和用户名都与字段一致；
- 时间戳格式；
- `index.json` 与各期文件是否一致；
- 话题数和帖子数是否在目标范围内（超出范围只给 warning）。

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
  "schema_version": 1, "date": "YYYY-MM-DD", "generated_at": "ISO8601Z",
  "window": {"start": "ISO8601Z", "end": "ISO8601Z"},
  "regions": [{"id": "west", "name_zh": "欧美"}, ...],
  "observations_zh": ["..."],
  "trends_snapshot": {"US": ["..."], ...},
  "topics": [{
    "id", "region", "rank", "categories": [..], "title_zh", "summary_zh", "why_youth_zh",
    "keywords": [..], "trend_hits": [..], "note_zh?",
    "heat": {"post_count": int, "query": str, "window": {...}, "source": "x.get_posts_counts_recent"},
    "posts": [{
      "id", "url", "author": {"username", "name", "followers"}, "created_at", "lang",
      "text", "text_zh", "note_zh?", "replies_note_zh?",
      "metrics": {"likes", "reposts", "replies", "quotes", "views", "bookmarks"},
      "replies": [{"id", "url", "author": {"username", "name"}, "created_at", "lang", "text", "text_zh", "likes"}]
    }]
  }],
  "meta": {"x_api_calls": int, "sources": [..], "limitations_zh": [..]}
}
```

`data/index.json`：`{"latest": "YYYY-MM-DD", "issues": [{"date", "topic_count", "post_count", "reply_count", "regions": {...}, "headline_zh"}]}`
