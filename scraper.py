"""
ZINE Event Calendar Scraper v3
対象: TABF, 文学フリマ, まちのZINEフェス, ZINEフェス(note),
      Art Book Osaka, コミティア, 関西コミティア, コミックマーケット
出力先: docs/events.json
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
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
    body_text = soup.get_text(separator="\n")
    year_match = re.search(r"TOKYO ART BOOK FAIR (\d{4})", body_text)
    year = year_match.group(1) if year_match else str(datetime.now().year)
    venue_match = re.search(r"会場[：:]\s*(.+)", body_text)
    venue = venue_match.group(1).strip().split("\n")[0] if venue_match else "東京都現代美術館"
    dates_raw = re.findall(r"(\d+)月(\d+)日", body_text)
    if dates_raw:
        first = dates_raw[0]
        last = dates_raw[-1]
        date_str = f"{year}-{int(first[0]):02d}-{int(first[1]):02d}"
        events.append({
            "title": "TOKYO ART BOOK FAIR",
            "date": date_str,
            "date_display": f"{year}年{first[0]}月{first[1]}日〜{last[0]}月{last[1]}日",
            "venue": venue,
            "url": "https://tokyoartbookfair.com/",
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
    soup = fetch("https://bunfree.net/event/")
    if not soup:
        print("[文学フリマ] フェッチ失敗 - スキップ")
        return events
    event_links = soup.find_all("a", href=re.compile(r"/event/[^/]+/?$"))
    for link in event_links[:10]:
        href = link.get("href", "")
        if not href.startswith("http"):
            href = "https://bunfree.net" + href
        text = link.get_text(strip=True)
        if not text or len(text) < 3:
            continue
        date_match = re.search(r"(\d{4})年?(\d{1,2})月(\d{1,2})日", text)
        date_str = ""
        if date_match:
            y, m, d = date_match.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
        events.append({
            "title": text,
            "date": date_str,
            "date_display": text,
            "venue": "各地会場",
            "url": href,
            "category": "文学フリマ",
            "source": "bunfree"
        })
    print(f"[文学フリマ] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 3. まちのZINEフェス
# ─────────────────────────────────────────────
def scrape_mzfest():
    events = []
    soup = fetch("https://mzfest.3zui.jp/")
    if not soup:
        return events
    nav_links = soup.find_all("a", href=re.compile(r"https://mzfest\.3zui\.jp/(?!#)"))
    event_pages = {}
    skip_paths = {"", "/", "/about", "/boothbreak"}
    for link in nav_links:
        href = link.get("href", "").rstrip("/")
        label = link.get_text(strip=True)
        path = href.replace("https://mzfest.3zui.jp", "")
        if path not in skip_paths and label and len(label) > 1:
            event_pages[href] = label
    for page_url, label in event_pages.items():
        page_soup = fetch(page_url)
        if not page_soup:
            continue
        page_text = page_soup.get_text(separator="\n")
        date_jp = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", page_text)
        date_en = re.search(r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s+(\d{1,2})", page_text)
        venue_match = re.search(r"場所\s*[：:]\s*([^\n]+)", page_text)
        venue = venue_match.group(1).strip() if venue_match else "関西各地"
        if date_jp:
            y, m, d = date_jp.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
            date_display = f"{y}年{m}月{d}日"
        elif date_en:
            month_map = {"JAN":1,"FEB":2,"MAR":3,"APR":4,"MAY":5,"JUN":6,
                         "JUL":7,"AUG":8,"SEP":9,"OCT":10,"NOV":11,"DEC":12}
            year = datetime.now().year
            m_num = month_map.get(date_en.group(1), 1)
            d_num = int(date_en.group(2))
            date_str = f"{year}-{m_num:02d}-{d_num:02d}"
            date_display = f"{year}年{m_num}月{d_num}日"
        else:
            continue
        events.append({
            "title": f"まちのZINEフェス {label}",
            "date": date_str,
            "date_display": date_display,
            "venue": venue[:50],
            "url": page_url,
            "category": "まちのZINEフェス",
            "source": "mzfest"
        })
    print(f"[まちのZINEフェス] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 4. ZINEフェス一覧 (note.com)
# ─────────────────────────────────────────────
def scrape_zinefes_note():
    events = []
    url = "https://note.com/bookcultureclub/n/n14764ff42f86"
    soup = fetch(url)
    if not soup:
        return events
    headings = soup.find_all(["h3", "h2"])
    current_year = datetime.now().year
    for h in headings:
        text = h.get_text(strip=True)
        match = re.match(r"[■▲●]?\s*ZINEフェス([^\・・\d]+)[・・](\d+)月(\d+)日", text)
        if not match:
            match = re.match(r"[■▲●]?\s*ZINEフェス([^\s\d]+)\s*[・・]?\s*(\d+)月(\d+)日", text)
        if not match:
            continue
        location = match.group(1).strip()
        month = int(match.group(2))
        day = int(match.group(3))
        now = datetime.now()
        year = current_year
        if month < now.month - 1:
            year = current_year + 1
        date_str = f"{year}-{month:02d}-{day:02d}"
        next_elem = h.find_next("a")
        event_url = next_elem.get("href", url) if next_elem else url
        if not event_url.startswith("http"):
            event_url = url
        status = "（出展受付終了）" if "出展受付終了" in text or "受付終了" in text else ""
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
# 5. Art Book Osaka
# ─────────────────────────────────────────────
def scrape_artbookosaka():
    events = []
    soup = fetch("https://artbookosaka.com/")
    if not soup:
        return events
    text = soup.get_text(separator="\n")

    # 開催日時パターン: "2026年 5月30日（土）～31日（日）"
    date_match = re.search(r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日", text)
    # 会場
    venue_match = re.search(r"会場[^\n]*\n([^\n]+)", text)
    venue = "シーサイドスタジオCASO（大阪）"
    if venue_match:
        venue = venue_match.group(1).strip()[:40]

    # イベント名（例: "Art Book Osaka 2026"）
    title_match = re.search(r"Art Book Osaka \d{4}", text)
    title = title_match.group(0) if title_match else "Art Book Osaka"

    if date_match:
        y, m, d = date_match.groups()
        date_str = f"{y}-{int(m):02d}-{int(d):02d}"
        # 終了日も探す
        end_match = re.search(
            r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日[^～\n]*[～〜]\s*(\d{1,2})日",
            text
        )
        if end_match:
            date_display = f"{y}年{m}月{d}日〜{end_match.group(4)}日"
        else:
            date_display = f"{y}年{m}月{d}日"

        events.append({
            "title": title,
            "date": date_str,
            "date_display": date_display,
            "venue": venue,
            "url": "https://artbookosaka.com/",
            "category": "アートブックフェア",
            "source": "artbookosaka"
        })
    print(f"[Art Book Osaka] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 6. コミティア（東京）
# ─────────────────────────────────────────────
def scrape_comitia():
    events = []
    soup = fetch("https://www.comitia.co.jp/html/schedule.html")
    if not soup:
        return events

    # h3タグ: "COMITIA156" などのタイトル
    sections = soup.find_all("h3")
    for section in sections:
        title_text = section.get_text(strip=True)
        if not re.match(r"COMITIA\d+", title_text):
            continue

        # 次の要素から日程・会場を取得
        next_p = section.find_next(["p", "div", "dl", "table"])
        block_text = ""
        # セクション以降のテキストをh3まで集める
        for sib in section.next_siblings:
            if sib.name == "h3":
                break
            if hasattr(sib, "get_text"):
                block_text += sib.get_text(separator="\n")

        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", block_text)
        venue_match = re.search(r"場所[：:]\s*([^\n]+)", block_text)
        venue = venue_match.group(1).strip() if venue_match else "東京ビッグサイト"

        if date_match:
            y, m, d = date_match.groups()
            # 日付が "xxxx" などプレースホルダーなら skip
            if "x" in y.lower() or "x" in m.lower():
                continue
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
            events.append({
                "title": title_text,
                "date": date_str,
                "date_display": f"{y}年{m}月{d}日",
                "venue": venue[:40],
                "url": "https://www.comitia.co.jp/html/schedule.html",
                "category": "コミティア",
                "source": "comitia"
            })

    print(f"[コミティア] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 7. 関西コミティア
# ─────────────────────────────────────────────
def scrape_k_comitia():
    events = []
    soup = fetch("https://www.k-comitia.com/")
    if not soup:
        return events
    text = soup.get_text(separator="\n")

    # h3タグで「関西コミティアXX」を探す
    headings = soup.find_all(["h3", "h2"])
    for h in headings:
        title_text = h.get_text(strip=True)
        if "関西コミティア" not in title_text:
            continue
        # 「見本誌読書会」は除外
        if "読書会" in title_text:
            continue

        # 次の要素から日程・会場を取得
        block_text = ""
        for sib in h.next_siblings:
            if sib.name in ["h2", "h3"]:
                break
            if hasattr(sib, "get_text"):
                block_text += sib.get_text(separator="\n")

        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", block_text)
        venue_match = re.search(r"開催場所\s*\n\s*([^\n]+)", block_text)
        venue = venue_match.group(1).strip() if venue_match else "インテックス大阪ほか"

        if date_match:
            y, m, d = date_match.groups()
            date_str = f"{y}-{int(m):02d}-{int(d):02d}"
            events.append({
                "title": title_text,
                "date": date_str,
                "date_display": f"{y}年{m}月{d}日",
                "venue": venue[:40],
                "url": "https://www.k-comitia.com/",
                "category": "コミティア",
                "source": "k_comitia"
            })

    print(f"[関西コミティア] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 8. コミックマーケット
#    トップページのWhat'sNewから最新回URLを動的に取得
# ─────────────────────────────────────────────
def scrape_comiket():
    events = []
    top_soup = fetch("https://www.comiket.co.jp/")
    if not top_soup:
        return events

    top_text = top_soup.get_text(separator="\n")

    # What'sNewから最新回のInfoページURLを探す（例: /info-a/C108/C108Info.html）
    info_links = top_soup.find_all("a", href=re.compile(r"/info-a/C\d+/C\d+Info\.html"))
    if not info_links:
        # フォールバック: テキストからC番号を取得して推測
        c_match = re.findall(r"C(\d{3})", top_text)
        if c_match:
            latest = max(set(c_match), key=lambda x: int(x))
            info_url = f"https://www.comiket.co.jp/info-a/C{latest}/C{latest}Info.html"
        else:
            print("[コミケ] URLを特定できませんでした")
            return events
    else:
        info_url = "https://www.comiket.co.jp" + info_links[0]["href"]

    info_soup = fetch(info_url)
    if not info_soup:
        return events

    info_text = info_soup.get_text(separator="\n")

    # タイトル（例: "コミックマーケット１０８"）
    title_match = re.search(r"コミックマーケット[１２３４５６７８９０\d]+", info_text)
    title = title_match.group(0) if title_match else "コミックマーケット"

    # 日程パターン
    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", info_text)
    # 会場
    venue_match = re.search(r"東京ビッグサイト[^\n]*", info_text)
    venue = "東京ビッグサイト"
    if venue_match:
        venue = venue_match.group(0)[:30]

    if date_match:
        y, m, d = date_match.groups()
        date_str = f"{y}-{int(m):02d}-{int(d):02d}"
        # 複数日程を探す（例: 12月28日・29日・30日）
        multiday = re.findall(r"(\d{1,2})月(\d{1,2})日", info_text)
        if len(multiday) >= 2:
            first = multiday[0]
            last = multiday[-1]
            date_display = f"{y}年{first[0]}月{first[1]}日〜{last[0]}月{last[1]}日"
        else:
            date_display = f"{y}年{m}月{d}日"

        events.append({
            "title": title,
            "date": date_str,
            "date_display": date_display,
            "venue": venue,
            "url": info_url,
            "category": "コミックマーケット",
            "source": "comiket"
        })

    print(f"[コミックマーケット] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 手動追加イベント（manual_events.json があれば読み込む）
# ─────────────────────────────────────────────
def load_manual_events():
    """
    docs/manual_events.json に手動でイベントを追加できる。
    フォーマット:
    [
      {
        "title": "イベント名",
        "date": "2026-06-20",
        "date_display": "2026年6月20日",
        "venue": "会場名",
        "url": "https://...",
        "category": "カテゴリ名",
        "source": "manual"
      }
    ]
    """
    path = "docs/manual_events.json"
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            events = json.load(f)
        print(f"[手動追加] {len(events)} events loaded")
        return events
    except Exception as e:
        print(f"[手動追加] 読み込みエラー: {e}")
        return []


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def run_all():
    all_events = []
    all_events += scrape_tabf()
    all_events += scrape_bunfree()
    all_events += scrape_mzfest()
    all_events += scrape_zinefes_note()
    all_events += scrape_artbookosaka()
    all_events += scrape_comitia()
    all_events += scrape_k_comitia()
    all_events += scrape_comiket()
    all_events += load_manual_events()   # 手動追加分

    all_events.sort(key=lambda e: e.get("date") or "9999-99-99")

    seen = set()
    unique_events = []
    for e in all_events:
        key = (e["title"], e["date"])
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    output = {
        "updated_at": datetime.now().isoformat(),
        "count": len(unique_events),
        "events": unique_events
    }

    os.makedirs("docs", exist_ok=True)
    with open("docs/events.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 合計 {len(unique_events)} イベントを docs/events.json に保存しました")
    return unique_events


if __name__ == "__main__":
    run_all()
