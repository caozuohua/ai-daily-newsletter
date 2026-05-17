# 🤖 AI & Agent 日报

每天北京时间 8:00 自动聚合 AI 与智能体领域最新动态，支持 **GitHub Pages RSS 订阅**、**Telegram 推送**、**Gmail 日报**，无需服务器，完全免费。

---

## 效果预览

- **RSS 订阅地址**：`https://YOUR_USERNAME.github.io/ai-rss-digest/feed.xml`
- **网页首页**：`https://YOUR_USERNAME.github.io/ai-rss-digest/`
- **历史报告**：仓库 `reports/` 目录，每天一个 Markdown 文件

---

## 覆盖的 RSS 源（22 个）

| 分类 | 来源 |
|------|------|
| 🔬 研究前沿 | Anthropic、OpenAI、DeepMind、Meta AI、arXiv cs.AI/LG、Lilian Weng、Ahead of AI、Interconnects |
| 🤖 智能体 | LangChain、LlamaIndex、AutoGen、Hugging Face |
| 📰 行业动态 | The Verge AI、MIT Tech Review、VentureBeat、TechCrunch、量子位、机器之心 |
| 🛠️ 技术博客 | Simon Willison、Towards Data Science、PaperWeekly |

在 `config/feeds.yaml` 中可自由增删。

---

## 快速开始

### 第一步：Fork 仓库

点击右上角 **Fork**，克隆到自己账号下。

### 第二步：开启 GitHub Pages

仓库 → **Settings → Pages → Source** 选择 **GitHub Actions**，保存。

### 第三步：配置推送渠道（至少选一个）

进入仓库 → **Settings → Secrets and variables → Actions → New repository secret**

**选项 A：Telegram（推荐，最简单）**

| Secret | 说明 |
|--------|------|
| `TELEGRAM_BOT_TOKEN` | Bot Token，从 @BotFather 获取 |
| `TELEGRAM_CHAT_ID` | 你的 Chat ID，见下方说明 |

获取 Chat ID：
1. Telegram 搜索 `@BotFather` → 发 `/newbot` → 按提示完成，复制 Token
2. 给刚创建的 Bot 发任意一条消息
3. 浏览器访问 `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. 从返回 JSON 中找 `"chat":{"id": 123456}` 这个数字即为 Chat ID

**选项 B：Gmail 日报**

| Secret | 说明 |
|--------|------|
| `SMTP_USER` | 你的 Gmail 地址 |
| `SMTP_PASS` | Gmail 应用专用密码（不是登录密码，见下方说明） |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `DIGEST_TO_EMAIL` | 收件地址（填自己即可） |

获取 Gmail 应用专用密码：
1. 打开 [myaccount.google.com/security](https://myaccount.google.com/security)，确认已开启两步验证
2. 搜索「应用专用密码」→ 应用名填 `rss-digest` → 点生成
3. 复制生成的 16 位密码，填入 `SMTP_PASS`

**选项 C：RSS 订阅（无需任何 Secret）**

只要完成第二步开启 Pages，RSS feed 会随每次 Actions 运行自动更新，用任意阅读器订阅 `feed.xml` 地址即可。推荐阅读器：Reeder（iOS/Mac）、Feedly、inoreader。

### 第四步：触发运行

推送代码后，每天 UTC 00:00（北京 08:00）自动运行。

也可以立即手动验证：仓库 → **Actions → AI & Agent Daily Digest → Run workflow**。

---

## 自定义 RSS 源

编辑 `config/feeds.yaml`：

```yaml
- name: "来源名称"
  url: "https://example.com/feed.xml"
  category: research    # research | agent | industry | product
  lang: en              # en | zh
```

调整抓取频率：

```yaml
digest:
  max_items_per_feed: 5    # 每个源最多取几条
  lookback_hours: 24       # 只收录过去 N 小时的内容
```

---

## 升级：接入 Claude AI 摘要

当前为免费版，输出按分类整理的条目列表。获得 [Anthropic API Key](https://console.anthropic.com/) 后，在 Secrets 中添加 `ANTHROPIC_API_KEY`，`digest.py` 中的 `ai_summarize()` 函数可替换为 Claude 调用，自动生成每日精选要点和行业洞察。

---

## 项目结构

```
ai-rss-digest/
├── .github/workflows/daily-digest.yml   # GitHub Actions 定时任务
├── config/feeds.yaml                    # RSS 源与推送配置
├── scripts/digest.py                    # 核心脚本
├── reports/                             # 每日 Markdown 报告（自动生成）
├── gh-pages/                            # Pages 静态文件（自动生成）
├── .cache/seen_ids.json                 # 去重缓存（自动生成）
└── requirements.txt
```

---

由 GitHub Actions 自动运行 · 无需服务器 · 完全免费
