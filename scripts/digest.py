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

# ─── 分类整理（免费版，无需 AI）────────────────────────────
def ai_summarize(items: list[dict], lang: str = "zh") -> str:
    """按分类聚合，输出 Markdown 列表，后续可替换为 Claude 摘要"""
    if not items:
        return "今日暂无新内容。"

    cat_labels = {
        "research": "🔬 研究前沿",
        "agent":    "🤖 智能体",
        "industry": "📰 行业动态",
        "product":  "🛠️ 技术产品",
    }
    by_cat: dict[str, list] = {}
    for item in items:
        by_cat.setdefault(item["category"], []).append(item)

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

    # 保存 Markdown 报告（同时作为 GitHub Pages / Artifact）
    report_path = BASE_DIR / "reports" / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(f"# {subject}\n\n{digest}\n\n---\n*自动生成于 {datetime.now().isoformat()}*")
    print(f"[OK] Report saved to {report_path}")

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
