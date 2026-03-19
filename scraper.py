"""
ZINE Event Calendar Scraper
対象: TABF, 文学フリマ, まちのZINEフェス, ZINEフェス(note)
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        res.encoding = res.apparent_encoding
        return BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"[FETCH ERROR] {url}: {e}")
        return None


# ─────────────────────────────────────────────
# 1. Tokyo Art Book Fair
# ─────────────────────────────────────────────
def scrape_tabf():
    events = []
    soup = fetch("https://tokyoartbookfair.com/")
    if not soup:
        return events

    # トップページの日時情報を取得
    body_text = soup.get_text(separator="\n")

    # 開催日程パターン（例: "12月11日（木）12:00-19:00"）
    date_pattern = re.findall(r"(\d+月\d+日[（(][^）)]+[）)])[\s　]*(\d+:\d+[-–]\d+:\d+)?", body_text)

    # イベント名と会場はトップページから固定情報として取得
    title_tag = soup.find("h1") or soup.find("title")
    title = "TOKYO ART BOOK FAIR"

    # 会場情報
    venue_match = re.search(r"会場[：:]\s*(.+)", body_text)
    venue = venue_match.group(1).strip().split("\n")[0] if venue_match else "東京都現代美術館"

    # 年度を特定
    year_match = re.search(r"TOKYO ART BOOK FAIR (\d{4})", body_text)
    year = year_match.group(1) if year_match else str(datetime.now().year)

    # 公式サイトURL
    url = "https://tokyoartbookfair.com/"

    # 日程をまとめて1イベントとして登録
    dates_raw = re.findall(r"(\d+)月(\d+)日", body_text)
    if dates_raw:
        # 最初と最後の日付でレンジを作る
        first = dates_raw[0]
        last = dates_raw[-1]
        date_str = f"{year}-{int(first[0]):02d}-{int(first[1]):02d}"

        events.append({
            "title": title,
            "date": date_str,
            "date_display": f"{year}年{first[0]}月{first[1]}日〜{last[0]}月{last[1]}日",
            "venue": venue,
            "url": url,
            "category": "アートブックフェア",
            "source": "tabf"
        })

    print(f"[TABF] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 2. 文学フリマ
# ─────────────────────────────────────────────
def scrape_bunfree():
    events = []

    # 文学フリマのイベント一覧ページ（複数URLを試す）
    urls_to_try = [
        "https://bunfree.net/event/",
        "https://bunfree.net/",
    ]

    soup = None
    for url in urls_to_try:
        soup = fetch(url)
        if soup:
            break

    if not soup:
        # フォールバック: 既知のイベント情報を返す
        print("[文学フリマ] フェッチ失敗 - スキップ")
        return events

    # イベントリンクを探す（/event/xxxxx/ パターン）
    event_links = soup.find_all("a", href=re.compile(r"/event/[^/]+/?$"))

    for link in event_links[:10]:  # 直近10件まで
        href = link.get("href", "")
        if not href.startswith("http"):
            href = "https://bunfree.net" + href

        text = link.get_text(strip=True)
        if not text or len(text) < 3:
            continue

        # 日付パターンを探す
        date_match = re.search(r"(\d{4})年?(\d{1,2})月(\d{1,2})日", text)
        if date_match:
            y, m, d = date_match.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
        else:
            date_str = ""

        events.append({
            "title": text if text else "文学フリマ",
            "date": date_str,
            "date_display": text,
            "venue": "各地会場",
            "url": href,
            "category": "文学フリマ",
            "source": "bunfree"
        })

    # イベントが見つからない場合、個別イベントページを試す
    if not events:
        # 直近イベントのURLパターンを試す
        current_year = datetime.now().year
        for city in ["tokyo", "osaka", "kyoto", "sapporo", "fukuoka"]:
            test_url = f"https://bunfree.net/event/{city}{current_year}/"
            test_soup = fetch(test_url)
            if test_soup:
                title_tag = test_soup.find("h1") or test_soup.find("h2")
                date_match = re.search(
                    r"(\d{4})年(\d{1,2})月(\d{1,2})日",
                    test_soup.get_text()
                )
                if date_match:
                    y, m, d = date_match.groups()
                    events.append({
                        "title": title_tag.get_text(strip=True) if title_tag else f"文学フリマ{city}",
                        "date": f"{y}-{int(m):02d}-{int(d):02d}",
                        "date_display": f"{y}年{m}月{d}日",
                        "venue": city,
                        "url": test_url,
                        "category": "文学フリマ",
                        "source": "bunfree"
                    })

    print(f"[文学フリマ] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 3. まちのZINEフェス (mzfest.3zui.jp) - Wixサイト
# ─────────────────────────────────────────────
def scrape_mzfest():
    events = []
    soup = fetch("https://mzfest.3zui.jp/")
    if not soup:
        return events

    text = soup.get_text(separator="\n")

    # ナビゲーションから各イベントページのリンクを取得
    nav_links = soup.find_all("a", href=re.compile(r"https://mzfest\.3zui\.jp/(?!#)"))

    # ページリンクとイベント名のマッピング
    event_pages = {}
    skip_paths = {"", "/", "/about", "/boothbreak"}
    for link in nav_links:
        href = link.get("href", "").rstrip("/")
        label = link.get_text(strip=True)
        path = href.replace("https://mzfest.3zui.jp", "")
        if path not in skip_paths and label and len(label) > 1:
            event_pages[href] = label

    # 各イベントページから日程を取得
    for page_url, label in event_pages.items():
        page_soup = fetch(page_url)
        if not page_soup:
            continue

        page_text = page_soup.get_text(separator="\n")

        # 日付パターン: "2026年3月14日" or "MAR 14 SAT"
        date_jp = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", page_text)
        date_en = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})", page_text)

        # 会場情報
        venue_match = re.search(r"場所\s*[：:]\s*([^\n]+)", page_text)
        venue = venue_match.group(1).strip() if venue_match else "関西各地"

        if date_jp:
            y, m, d = date_jp.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
            date_display = f"{y}年{m}月{d}日"
        elif date_en:
            # 英語日付から変換
            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
                "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
                "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
            }
            year = datetime.now().year
            m_num = month_map.get(date_en.group(1), 1)
            d_num = int(date_en.group(2))
            date_str = f"{year}-{m_num:02d}-{d_num:02d}"
            date_display = f"{year}年{m_num}月{d_num}日"
        else:
            continue

        # イベントタイトル
        h1 = page_soup.find("h1") or page_soup.find("h2")
        title = h1.get_text(strip=True) if h1 else label

        events.append({
            "title": f"まちのZINEフェス {label}",
            "date": date_str,
            "date_display": date_display,
            "venue": venue[:50],
            "url": page_url,
            "category": "ZINEフェス",
            "source": "mzfest"
        })

    print(f"[まちのZINEフェス] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 4. ZINEフェス一覧 (note.com/bookcultureclub)
# ─────────────────────────────────────────────
def scrape_zinefes_note():
    events = []
    url = "https://note.com/bookcultureclub/n/n14764ff42f86"
    soup = fetch(url)
    if not soup:
        return events

    # h3タグ: "■ZINEフェス仙台・2月28日" 形式
    headings = soup.find_all(["h3", "h2"])

    current_year = datetime.now().year

    for h in headings:
        text = h.get_text(strip=True)

        # "■ZINEフェスXXX・M月D日" のパターン
        match = re.match(r"[■▲●]?\s*ZINEフェス([^\・・]+)[・・](\d+)月(\d+)日", text)
        if not match:
            # "ZINEフェスXXX・M/D" 形式も試す
            match = re.match(r"[■▲●]?\s*ZINEフェス([^\s\d]+)\s*[・・]?\s*(\d+)月(\d+)日", text)

        if not match:
            continue

        location = match.group(1).strip()
        month = int(match.group(2))
        day = int(match.group(3))

        # 年度判定（月が現在より前なら翌年）
        now = datetime.now()
        year = current_year
        if month < now.month - 1:
            year = current_year + 1

        date_str = f"{year}-{month:02d}-{day:02d}"

        # URLはnoteの記事内リンクを探す
        next_elem = h.find_next("a")
        event_url = next_elem.get("href", url) if next_elem else url
        if not event_url.startswith("http"):
            event_url = url

        # 受付状況
        status = ""
        if "出展受付終了" in text or "受付終了" in text:
            status = "（出展受付終了）"

        events.append({
            "title": f"ZINEフェス{location}{status}",
            "date": date_str,
            "date_display": f"{year}年{month}月{day}日",
            "venue": location,
            "url": event_url,
            "category": "ZINEフェス",
            "source": "zinefes_note"
        })

    print(f"[ZINEフェス/note] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# メイン: 全ソースを集約してJSONに保存
# ─────────────────────────────────────────────
def run_all():
    all_events = []

    all_events += scrape_tabf()
    all_events += scrape_bunfree()
    all_events += scrape_mzfest()
    all_events += scrape_zinefes_note()

    # 日付でソート（日付なしは末尾）
    def sort_key(e):
        return e.get("date") or "9999-99-99"

    all_events.sort(key=sort_key)

    # 重複除去（title + date が同じものを省く）
    seen = set()
    unique_events = []
    for e in all_events:
        key = (e["title"], e["date"])
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    # JSONに保存
    output = {
        "updated_at": datetime.now().isoformat(),
        "count": len(unique_events),
        "events": unique_events
    }

    with open("events.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 合計 {len(unique_events)} イベントを events.json に保存しました")
    return unique_events


if __name__ == "__main__":
    run_all()
