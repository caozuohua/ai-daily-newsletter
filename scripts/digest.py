#!/usr/bin/env python3
"""
AI & Agent Daily RSS Digest (免费版 · 无需 API Key)
每日自动拉取RSS → 分类整理 → 多渠道推送
"""

import os
import json
import time
import smtplib
import hashlib
import requests
import feedparser
import yaml
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─── 配置 ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config" / "feeds.yaml"
CACHE_PATH = BASE_DIR / ".cache" / "seen_ids.json"

# ─── 工具函数 ──────────────────────────────────────────────
def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)

def load_cache():
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CACHE_PATH.exists():
        return set(json.loads(CACHE_PATH.read_text()))
    return set()

def save_cache(seen: set):
    # 只保留最近 3000 条，防止文件膨胀
    items = list(seen)[-3000:]
    CACHE_PATH.write_text(json.dumps(items))

def item_id(entry) -> str:
    raw = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.md5(raw.encode()).hexdigest()

def parse_time(entry) -> datetime:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)

# ─── 拉取 RSS ─────────────────────────────────────────────
def fetch_feeds(config: dict, seen: set, lookback_hours: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    max_per = config["digest"]["max_items_per_feed"]
    results = []

    for feed_cfg in config["feeds"]:
        try:
            d = feedparser.parse(feed_cfg["url"])
            count = 0
            for entry in d.entries:
                if count >= max_per:
                    break
                eid = item_id(entry)
                if eid in seen:
                    continue
                pub = parse_time(entry)
                if pub < cutoff:
                    continue
                results.append({
                    "id": eid,
                    "source": feed_cfg["name"],
                    "category": feed_cfg["category"],
                    "lang": feed_cfg.get("lang", "en"),
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:800],
                    "published": pub.strftime("%Y-%m-%d %H:%M UTC"),
                })
                seen.add(eid)
                count += 1
            time.sleep(0.3)  # 礼貌爬取
        except Exception as e:
            print(f"[WARN] Failed to fetch {feed_cfg['name']}: {e}")

    # 按发布时间倒序
    results.sort(key=lambda x: x["published"], reverse=True)
    return results

# ─── AI 摘要（通过 VertexAI / Google AI Studio 免费额度）───────
def ai_summarize(items: list[dict], lang: str = "zh") -> str:
    """调用 LLM 生成中文 AI 摘要，fallback 到规则摘要"""
    if not items:
        return "今日暂无新内容。"

    cat_labels = {
        "research": "🔬 研究前沿",
        "agent":    "🤖 智能体",
        "industry": "📰 行业动态",
        "product":  "🛠️ 产品技术",
    }

    # 按分类聚合
    by_cat: dict[str, list] = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    # 构建摘要输入
    lines = []
    for cat, label in cat_labels.items():
        cat_items = by_cat.get(cat, [])
        if not cat_items:
            continue
        lines.append(f"【{label}】")
        for item in cat_items:
            title = item["title"]
            source = item["source"]
            summary = item.get("summary", "")[:200]
            lines.append(f"- {title}（{source}）")
            if summary:
                lines.append(f"  简介：{summary}")
        lines.append("")

    prompt = f"""你是一位 AI 行业分析师。以下是今天收集的 {len(items)} 条 AI/Agent 领域新闻。
请用中文生成一段简洁的「AI 日报摘要」（300 字以内），要求：
1. 按板块（研究前沿/智能体/行业动态/产品技术）各用 1-2 句话总结亮点
2. 指出最值得关注的 2-3 条新闻，简述原因
3. 最后用一句话总结今日趋势
4. 语言精炼、专业，面向技术从业者

原始数据：
{chr(10).join(lines)}"""

    # 尝试通过 OpenAI 兼容 API 调用（VertexAI 代理 / Google AI Studio）
    try:
        import os
        from openai import OpenAI

        base_url = os.environ.get("VERTEXAI_PROXY_URL", "http://127.0.0.1:18999/v1")
        api_key = os.environ.get("VERTEXAI_PROXY_KEY", "placeholder")
        model = os.environ.get("LLM_MODEL", "gemini-3.5-flash")

        client = OpenAI(base_url=base_url, api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.7,
            extra_body={"google": {"thinking_config": {"include_thoughts": False, "thinking_budget": 0}}},
        )
        result_text = resp.choices[0].message.content.strip()
        if result_text:
            return result_text
        print(f"[WARN] LLM 返回空内容 (finish_reason={resp.choices[0].finish_reason})")
    except ImportError:
        print("[WARN] openai 未安装，使用规则摘要")
    except Exception as e:
        print(f"[WARN] LLM 摘要失败({e})，使用规则摘要")

    return _fallback_summary(items, by_cat, cat_labels, lang)


def _fallback_summary(items, by_cat, cat_labels, lang) -> str:
    """规则摘要（Gemini 不可用时的后备）"""
    lines = [f"共收录 **{len(items)}** 条更新\n"]
    for cat, label in cat_labels.items():
        cat_items = by_cat.get(cat, [])
        if not cat_items:
            continue
        lines.append(f"\n## {label}\n")
        for item in cat_items:
            lines.append(
                f"- [{item['title']}]({item['link']})  \n"
                f"  *{item['source']} · {item['published']}*"
            )
    return "\n".join(lines)

# ─── 生成 HTML 邮件 ───────────────────────────────────────
def build_html(ai_digest: str, items: list[dict], date_str: str) -> str:
    by_cat = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

    cat_labels = {
        "research": "🔬 研究前沿",
        "agent": "🤖 智能体",
        "industry": "📰 行业动态",
        "product": "🛠️ 产品技术",
    }

    sections_html = ""
    for cat, label in cat_labels.items():
        cat_items = by_cat.get(cat, [])
        if not cat_items:
            continue
        rows = "".join(
            f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0">'
            f'<a href="{i["link"]}" style="color:#1a73e8;text-decoration:none;font-size:14px">{i["title"]}</a>'
            f'<span style="color:#999;font-size:12px;margin-left:8px">{i["source"]} · {i["published"]}</span>'
            f'</td></tr>'
            for i in cat_items
        )
        sections_html += f"""
        <h3 style="color:#444;font-size:15px;margin:20px 0 8px">{label}</h3>
        <table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
        """

    # 将 Markdown 链接转为 HTML（简单替换，无需库）
    import re
    ai_html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', ai_digest)
    ai_html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', ai_html)
    ai_html = re.sub(r'^## (.+)$', r'<h3 style="color:#667eea;margin:16px 0 6px">\1</h3>', ai_html, flags=re.MULTILINE)
    ai_html = re.sub(r'^- (.+)$', r'<p style="margin:4px 0 4px 12px">· \1</p>', ai_html, flags=re.MULTILINE)
    ai_html = ai_html.replace('\n', '')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:700px;margin:0 auto;padding:20px;color:#333">
  <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;border-radius:12px;color:white;margin-bottom:24px">
    <h1 style="margin:0;font-size:22px">🚀 AI & Agent 日报</h1>
    <p style="margin:6px 0 0;opacity:0.85">{date_str} · {len(items)} 条新内容</p>
  </div>

  <div style="background:#f8f9ff;border-left:4px solid #667eea;padding:16px 20px;border-radius:0 8px 8px 0;margin-bottom:24px">
    <h2 style="margin:0 0 12px;font-size:16px;color:#667eea">🧠 AI 精选摘要</h2>
    <div style="font-size:14px;line-height:1.7">{ai_html}</div>
  </div>

  <div>
    <h2 style="font-size:16px;color:#444;border-bottom:2px solid #eee;padding-bottom:8px">📋 全部更新</h2>
    {sections_html}
  </div>

  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #eee;color:#999;font-size:12px;text-align:center">
    由 GitHub Actions 自动生成 · <a href="https://github.com" style="color:#999">查看项目</a>
  </div>
</body></html>"""

# ─── 推送渠道 ──────────────────────────────────────────────
def send_email(html: str, subject: str):
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr   = os.environ["DIGEST_TO_EMAIL"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.sendmail(smtp_user, to_addr, msg.as_string())
    print(f"[OK] Email sent to {to_addr}")

def send_telegram(text: str):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return
    # Telegram 消息限制 4096 字
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"},
            timeout=10
        )
    print("[OK] Telegram sent")

def send_webhook(payload: dict):
    url = os.environ.get("WEBHOOK_URL")
    if not url:
        return
    requests.post(url, json=payload, timeout=10)
    print("[OK] Webhook sent")

# ─── 生成 RSS feed.xml ────────────────────────────────────
def build_feed(items: list[dict], repo_url: str) -> str:
    """生成标准 Atom feed，供 RSS 阅读器订阅"""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    entries = ""
    for item in items[:50]:  # feed 最多保留 50 条
        entries += f"""
  <entry>
    <title>{esc(item['title'])}</title>
    <link href="{esc(item['link'])}"/>
    <id>{esc(item['link'])}</id>
    <updated>{item['published'].replace(' UTC', 'Z').replace(' ', 'T')}</updated>
    <author><name>{esc(item['source'])}</name></author>
    <category term="{esc(item['category'])}"/>
    <summary>{esc(item['summary'][:300])}</summary>
  </entry>"""

    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>🤖 AI &amp; Agent 日报</title>
  <subtitle>每日自动聚合 AI 与智能体领域最新动态</subtitle>
  <link href="{repo_url}/feed.xml" rel="self"/>
  <link href="{repo_url}"/>
  <id>{repo_url}/feed.xml</id>
  <updated>{now_iso}</updated>
  <generator>GitHub Actions RSS Digest</generator>
{entries}
</feed>"""

def build_index_html(items: list[dict], date_str: str, repo_url: str) -> str:
    """生成 GitHub Pages 首页，内嵌 RSS 自动发现"""
    import re
    rows = ""
    for item in items:
        cat_color = {"research": "#667eea", "agent": "#f093fb", "industry": "#4facfe", "product": "#43e97b"}.get(item["category"], "#aaa")
        rows += (
            f'<tr><td style="padding:8px 4px;border-bottom:1px solid #f0f0f0;vertical-align:top">'
            f'<span style="background:{cat_color};color:white;border-radius:3px;padding:1px 6px;font-size:11px">{item["category"]}</span></td>'
            f'<td style="padding:8px;border-bottom:1px solid #f0f0f0">'
            f'<a href="{item["link"]}" style="color:#1a73e8;text-decoration:none">{item["title"]}</a>'
            f'<div style="color:#999;font-size:12px;margin-top:2px">{item["source"]} · {item["published"]}</div></td></tr>'
        )
    return f"""<!DOCTYPE html>
<html lang="zh"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🤖 AI & Agent 日报</title>
<link rel="alternate" type="application/atom+xml" title="AI &amp; Agent 日报 RSS" href="{repo_url}/feed.xml">
<style>body{{font-family:-apple-system,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#333}}
a.rss-btn{{display:inline-block;background:#f5a623;color:white;padding:8px 16px;border-radius:6px;text-decoration:none;font-size:14px;margin-top:8px}}</style>
</head><body>
<div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:24px;border-radius:12px;color:white;margin-bottom:24px">
  <h1 style="margin:0;font-size:22px">🤖 AI & Agent 日报</h1>
  <p style="margin:6px 0 12px;opacity:0.85">最后更新：{date_str} · 共 {len(items)} 条</p>
  <a class="rss-btn" href="{repo_url}/feed.xml">🔔 订阅 RSS Feed</a>
</div>
<table width="100%" cellpadding="0" cellspacing="0">{rows}</table>
<p style="color:#999;font-size:12px;text-align:center;margin-top:32px">由 GitHub Actions 每日自动生成</p>
</body></html>"""

# ─── 主流程 ───────────────────────────────────────────────
def main():
    print("=== AI RSS Digest starting ===")
    config   = load_config()
    seen     = load_cache()
    lookback = config["digest"]["lookback_hours"]
    lang     = config["digest"]["summary_lang"]

    print(f"Fetching feeds (lookback={lookback}h)...")
    items = fetch_feeds(config, seen, lookback)
    print(f"Found {len(items)} new items")

    if not items:
        print("No new items, skipping digest.")
        save_cache(seen)
        return

    print("Grouping items by category...")
    digest = ai_summarize(items, lang)

    date_str  = datetime.now().strftime("%Y年%m月%d日")
    subject   = f"🤖 AI & Agent 日报 · {date_str} ({len(items)} 条)"

    # 保存 Markdown 报告
    report_path = BASE_DIR / "reports" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(f"# {subject}\n\n{digest}\n\n---\n*自动生成于 {datetime.now().isoformat()}*")
    print(f"[OK] Report saved to {report_path}")

    # 生成 GitHub Pages 静态文件（feed.xml + index.html）
    repo_url  = os.environ.get("PAGES_URL", "https://YOUR_USERNAME.github.io/ai-rss-digest")
    pages_dir = BASE_DIR / "gh-pages"
    pages_dir.mkdir(exist_ok=True)
    (pages_dir / "feed.xml").write_text(build_feed(items, repo_url), encoding="utf-8")
    (pages_dir / "index.html").write_text(build_index_html(items, date_str, repo_url), encoding="utf-8")
    print(f"[OK] GitHub Pages files written to {pages_dir}")

    # 推送
    PUSH_EMAIL    = os.environ.get("SMTP_USER") and os.environ.get("DIGEST_TO_EMAIL")
    PUSH_TELEGRAM = os.environ.get("TELEGRAM_BOT_TOKEN")

    if PUSH_EMAIL:
        html = build_html(digest, items, date_str)
        send_email(html, subject)

    if PUSH_TELEGRAM:
        send_telegram(f"*{subject}*\n\n{digest}")

    send_webhook({"subject": subject, "digest": digest, "count": len(items)})

    save_cache(seen)
    print("=== Done ===")

if __name__ == "__main__":
    main()
