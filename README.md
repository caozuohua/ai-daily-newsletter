# 🤖 AI & Agent Daily Digest

> 每日自动拉取 AI/智能体领域 RSS → Claude AI 精选摘要 → 多渠道推送

## 功能

- **20+ 精选 RSS 源**：覆盖 Anthropic、OpenAI、DeepMind、arXiv、LangChain、量子位等
- **Claude AI 摘要**：自动提炼每日要点和行业洞察
- **多渠道推送**：邮件 / Telegram / 自定义 Webhook（按需配置）
- **去重缓存**：不重复推送同一条内容
- **GitHub Actions**：每天北京时间 8:00 自动运行，无需服务器

## 快速开始

### 1. Fork / Clone 仓库

```bash
git clone https://github.com/YOUR_USERNAME/ai-rss-digest.git
cd ai-rss-digest
```

### 2. 配置 Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions 中添加：

| Secret | 必填 | 说明 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API Key |
| `SMTP_USER` | 邮件推送 | 发件邮箱（如 Gmail） |
| `SMTP_PASS` | 邮件推送 | 邮箱授权码 |
| `SMTP_HOST` | 邮件推送 | 默认 `smtp.gmail.com` |
| `SMTP_PORT` | 邮件推送 | 默认 `587` |
| `DIGEST_TO_EMAIL` | 邮件推送 | 收件邮箱 |
| `TELEGRAM_BOT_TOKEN` | Telegram | Bot Token |
| `TELEGRAM_CHAT_ID` | Telegram | Chat ID（个人/群组） |
| `WEBHOOK_URL` | Webhook | 自定义 POST 地址 |

### 3. 启用 Actions

推送代码后，Actions 会在每天 UTC 00:00（北京 08:00）自动运行。
也可在 Actions 页面点击 **Run workflow** 手动触发。

## Gmail 配置说明

1. Google 账号 → 安全 → 两步验证（需开启）
2. 搜索"应用专用密码"，生成一个，填入 `SMTP_PASS`
3. `SMTP_USER` 填写你的 Gmail 地址

## Telegram Bot 配置说明

1. 找 @BotFather 创建 Bot，获得 Token
2. 给 Bot 发一条消息，然后访问：
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. 从响应中取 `chat.id` 填入 `TELEGRAM_CHAT_ID`

## 自定义 RSS 源

编辑 `config/feeds.yaml`，按格式添加/删除源：

```yaml
- name: "你的源名称"
  url: "https://example.com/feed.xml"
  category: research   # research | agent | industry | product
  lang: en             # en | zh
```

## 项目结构

```
ai-rss-digest/
├── .github/workflows/daily-digest.yml   # GitHub Actions
├── config/feeds.yaml                     # RSS 源配置
├── scripts/digest.py                     # 核心脚本
├── reports/                              # 每日报告（自动生成）
├── .cache/seen_ids.json                  # 去重缓存（自动生成）
└── requirements.txt
```

## 报告示例

每次运行后，报告自动提交到 `reports/YYYY-MM-DD.md`，可直接在 GitHub 查看。

---
Powered by Claude AI + GitHub Actions
