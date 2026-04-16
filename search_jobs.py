"""
案件収集スクリプト
クラウドワークス・ランサーズから新着案件を取得し、Gmail通知を送る
"""

import os
import time
import json
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup

# ==============================
# 設定
# ==============================

GMAIL_FROM    = os.environ.get("GMAIL_FROM", "")      # 送信元Gmailアドレス
GMAIL_TO      = os.environ.get("GMAIL_TO", "")        # 送信先アドレス（同じでもOK）
GMAIL_APP_PW  = os.environ.get("GMAIL_APP_PW", "")    # Gmailアプリパスワード

KEYWORDS = [
    "WordPress",
    "ワードプレス",
    "HP修正",
    "ホームページ修正",
    "LP制作",
    "コーディング",
    "HTML CSS",
    "Python 自動化",
    "SEO 記事",
]

# 除外ワード（タイトルにこれが含まれていたらスキップ）
EXCLUDE_KEYWORDS = [
    "スパム", "副業", "マルチ", "投資", "FX",
    "現地", "出社必須", "勤務地",
]

SEEN_FILE = "seen_jobs.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}


# ==============================
# 既読管理
# ==============================

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


# ==============================
# Lancers スクレイピング
# ==============================

def search_lancers(keyword: str) -> list[dict]:
    url = (
        f"https://www.lancers.jp/work/search"
        f"?keyword={requests.utils.quote(keyword)}"
        f"&work_type%5B%5D=1&sort=new&open=1"
    )
    jobs = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        # 案件カードを取得（ランサーズのHTML構造）
        cards = soup.select(".p-work-list__item, .work-list-item, article.p-search-result__item")
        if not cards:
            # 別のセレクタを試す
            cards = soup.select("li.search-result-item, div.c-media")

        for card in cards[:10]:
            title_el = card.select_one("a.p-work-title, h3 a, .work-title a, a[href*='/work/detail/']")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.lancers.jp" + href

            price_el = card.select_one(".p-work-price, .work-price, .price")
            price = price_el.get_text(strip=True) if price_el else "要確認"

            desc_el = card.select_one(".p-work-description, .work-description, .description")
            desc = desc_el.get_text(strip=True)[:100] if desc_el else ""

            jobs.append({
                "platform": "ランサーズ",
                "title": title,
                "price": price,
                "description": desc,
                "url": href,
                "keyword": keyword,
            })
    except Exception as e:
        print(f"[Lancers ERROR] {keyword}: {e}")
    return jobs


# ==============================
# クラウドワークス（RSS）
# ==============================

def search_crowdworks(keyword: str) -> list[dict]:
    """RSSフィードを使って案件を取得"""
    rss_url = (
        f"https://crowdworks.jp/public/jobs.rss"
        f"?order=new&job_type=1&search%5Bkeyword%5D={requests.utils.quote(keyword)}"
    )
    jobs = []
    try:
        res = requests.get(rss_url, headers=HEADERS, timeout=15)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "xml")

        items = soup.find_all("item")
        for item in items[:10]:
            title = item.find("title")
            link = item.find("link")
            desc = item.find("description")

            if not title or not link:
                continue

            title_text = title.get_text(strip=True)
            link_text = link.get_text(strip=True) if link.get_text(strip=True).startswith("http") else link.next_sibling

            desc_text = ""
            if desc:
                desc_soup = BeautifulSoup(desc.get_text(), "html.parser")
                desc_text = desc_soup.get_text(strip=True)[:100]

            jobs.append({
                "platform": "クラウドワークス",
                "title": title_text,
                "price": "詳細を確認",
                "description": desc_text,
                "url": str(link_text).strip(),
                "keyword": keyword,
            })
    except Exception as e:
        print(f"[CrowdWorks ERROR] {keyword}: {e}")
    return jobs


# ==============================
# フィルタリング
# ==============================

def is_valid_job(job: dict) -> bool:
    title = job["title"].lower()
    for ex in EXCLUDE_KEYWORDS:
        if ex.lower() in title:
            return False
    return True


# ==============================
# Gmail通知
# ==============================

def send_gmail(subject: str, body_html: str):
    if not GMAIL_FROM or not GMAIL_APP_PW:
        print("[Gmail] 認証情報が未設定のためスキップ")
        print(body_html)
        return
    to = GMAIL_TO or GMAIL_FROM  # 送信先未設定なら自分宛て

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_FROM
    msg["To"] = to
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_FROM, GMAIL_APP_PW)
            server.sendmail(GMAIL_FROM, to, msg.as_string())
        print(f"[Gmail] 送信成功 → {to}")
    except Exception as e:
        print(f"[Gmail ERROR] {e}")


def format_job_html(jobs: list[dict]) -> tuple[str, str]:
    """(subject, html_body) を返す"""
    now = datetime.now().strftime("%Y/%m/%d %H:%M")
    subject = f"【案件通知】新着 {len(jobs)}件 ({now})"

    rows = []
    for i, job in enumerate(jobs, 1):
        rows.append(f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:12px 8px; font-weight:bold; color:#444;">{i}</td>
          <td style="padding:12px 8px;">
            <div style="font-size:15px; font-weight:bold;">
              <a href="{job['url']}" style="color:#1a73e8; text-decoration:none;">{job['title']}</a>
            </div>
            <div style="color:#888; font-size:12px; margin-top:4px;">{job['platform']} ／ キーワード: {job['keyword']}</div>
            <div style="color:#555; font-size:13px; margin-top:4px;">{job['description']}</div>
          </td>
          <td style="padding:12px 8px; white-space:nowrap; color:#e67e22; font-weight:bold;">{job['price']}</td>
        </tr>""")

    body = f"""
    <html><body style="font-family:'Helvetica Neue',Arial,sans-serif; color:#333; max-width:700px; margin:0 auto; padding:20px;">
      <h2 style="color:#1a73e8; border-bottom:2px solid #1a73e8; padding-bottom:8px;">
        🔍 新着案件 {len(jobs)}件 — {now}
      </h2>
      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr style="background:#f5f5f5;">
            <th style="padding:8px; text-align:left; width:30px;">#</th>
            <th style="padding:8px; text-align:left;">案件</th>
            <th style="padding:8px; text-align:left;">単価</th>
          </tr>
        </thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
      <p style="color:#aaa; font-size:11px; margin-top:20px;">このメールは自動送信されました。</p>
    </body></html>"""

    return subject, body


# ==============================
# メイン処理
# ==============================

def main():
    print(f"[{datetime.now()}] 案件収集を開始")
    seen = load_seen()
    all_new_jobs = []

    for keyword in KEYWORDS:
        print(f"  検索中: {keyword}")
        lancers_jobs = search_lancers(keyword)
        cw_jobs = search_crowdworks(keyword)
        all_jobs = lancers_jobs + cw_jobs
        time.sleep(1)  # サーバー負荷軽減

        for job in all_jobs:
            jid = job_id(job["url"])
            if jid not in seen and is_valid_job(job):
                all_new_jobs.append(job)
                seen.add(jid)

    # 重複除去（URLで）
    seen_urls = set()
    unique_jobs = []
    for job in all_new_jobs:
        if job["url"] not in seen_urls:
            unique_jobs.append(job)
            seen_urls.add(job["url"])

    print(f"新着案件: {len(unique_jobs)}件")

    # ダッシュボード用 jobs.json を更新（新着がなくても更新時刻を記録）
    save_jobs_json(unique_jobs)

    if unique_jobs:
        subject, body = format_job_html(unique_jobs)
        send_gmail(subject, body)
    else:
        print("新着案件なし")

    save_seen(seen)
    print("完了")


# ==============================
# ダッシュボード用 JSON 保存
# ==============================

JOBS_JSON = "docs/jobs.json"

def save_jobs_json(new_jobs: list[dict]):
    """既存のjobs.jsonに新着を追記し、最新300件に絞って保存"""
    os.makedirs("docs", exist_ok=True)
    existing = []
    if os.path.exists(JOBS_JSON):
        with open(JOBS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            existing = data.get("jobs", [])

    # 既存URLセット（重複防止）
    existing_urls = {j["url"] for j in existing}
    for job in new_jobs:
        if job["url"] not in existing_urls:
            job["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            existing.insert(0, job)
            existing_urls.add(job["url"])

    # 最新300件に絞る
    existing = existing[:300]

    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": len(existing),
        "jobs": existing,
    }
    with open(JOBS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[JSON] docs/jobs.json を更新 ({len(existing)}件)")


if __name__ == "__main__":
    main()
