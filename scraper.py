"""
ZINE Event Calendar Scraper v6
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime, date, timedelta

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def fetch(url, encoding=None):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        if encoding:
            res.encoding = encoding
        else:
            res.encoding = res.apparent_encoding
        return BeautifulSoup(res.text, "html.parser")
    except Exception as e:
        print(f"[FETCH ERROR] {url}: {e}")
        return None

def fetch_text(url, encoding=None):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        if encoding:
            res.encoding = encoding
        else:
            res.encoding = res.apparent_encoding
        return res.text
    except Exception as e:
        print(f"[FETCH ERROR] {url}: {e}")
        return ""


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
        events.append({
            "title": "TOKYO ART BOOK FAIR",
            "date": f"{year}-{int(first[0]):02d}-{int(first[1]):02d}",
            "date_display": f"{year}年{first[0]}月{first[1]}日〜{last[0]}月{last[1]}日",
            "venue": venue,
            "url": "https://tokyoartbookfair.com/",
            "category": "アートブックフェア",
            "source": "tabf"
        })
    print(f"[TABF] {len(events)} events found")
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
ZINEFES_LIST_URL = "https://note.com/bookcultureclub/n/n14764ff42f86"

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

# 見出しの例
#   ■ZINEフェス東京・9月26日
#   ■ZINEフェス文芸・詩歌と日記・8月2日
#   ■ZINEフェス福島・27年1月10日
ZINEFES_HEADING_RE = re.compile(
    r"^[■▲●・\s]*ZINEフェス"
    r"(?P<loc>.+?)"
    r"[・･]?\s*"
    r"(?:(?P<yy>\d{2})年)?\s*"
    r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
)

# note の個別記事URLだけを対象にする（ハッシュタグやプロフィールを拾わないため）
NOTE_ARTICLE_RE = re.compile(r"^https?://note\.com/[\w.\-]+/n/\w+")


def _link_in_section(heading):
    """見出しから次の見出しまでの間にあるnote記事リンクだけを返す。

    修正前は find_next("a") で「文書内の次のリンク」を拾っていたため、
    案内ページが未公開（受付前・募集前）でリンクが貼られていない回があると、
    ひとつ下のイベントのリンクを取り込んでしまっていた。
    （例：ZINEフェス東京12月5日 → ZINEフェス島根12月6日のURL）
    """
    for elem in heading.find_all_next():
        if elem.name in HEADING_TAGS:
            break
        if elem.name == "a":
            href = (elem.get("href") or "").strip()
            if NOTE_ARTICLE_RE.match(href):
                return href
    return None


def _resolve_year(yy, month, day):
    """見出しに「27年」などの表記があればそれを優先、なければ直近の開催年を推定する。"""
    if yy:
        return 2000 + int(yy)
    today = date.today()
    year = today.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return year
    # 一覧では翌年分に「27年」等の表記が付くため、年表記なしの過去日は
    # 基本的に当年扱いにする（過去イベントは表示側で非表示になる）。
    # 半年以上前の日付だけ、翌年の回とみなして繰り上げる。
    if candidate < today - timedelta(days=180):
        year += 1
    return year


def scrape_zinefes_note():
    events = []
    soup = fetch(ZINEFES_LIST_URL)
    if not soup:
        return events

    fallback_count = 0
    for h in soup.find_all(HEADING_TAGS):
        text = h.get_text(strip=True)
        match = ZINEFES_HEADING_RE.match(text)
        if not match:
            continue

        location = re.sub(r"[【\[].*?[】\]]", "", match.group("loc"))
        location = location.strip(" 　・･＠@")
        if not location:
            continue
        if any(ng in location for ng in ("●", "○", "〇", "未確定", "未定")):
            continue

        month = int(match.group("month"))
        day = int(match.group("day"))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            continue
        year = _resolve_year(match.group("yy"), month, day)

        event_url = _link_in_section(h)
        if not event_url:
            # 案内ページが未公開の回は、他イベントのURLを流用せず一覧ページへ誘導する
            event_url = ZINEFES_LIST_URL
            fallback_count += 1

        status = "（出展受付終了）" if "受付終了" in text else ""
        events.append({
            "title": f"ZINEフェス{location}{status}",
            "date": f"{year}-{month:02d}-{day:02d}",
            "date_display": f"{year}年{month}月{day}日",
            "venue": location,
            "url": event_url,
            "category": "ZINEフェス",
            "source": "zinefes_note"
        })

    print(f"[ZINEフェス/note] {len(events)} events found "
          f"（案内ページ未公開のため一覧ページを指した回: {fallback_count}）")
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
    title_match = re.search(r"Art Book Osaka \d{4}", text)
    title = title_match.group(0) if title_match else "Art Book Osaka"
    date_match = re.search(r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日", text)
    if date_match:
        y, m, d = date_match.groups()
        end_match = re.search(
            r"(\d{4})年\s*(\d{1,2})月(\d{1,2})日[^～\n]*[～〜]\s*(\d{1,2})日", text)
        date_display = f"{y}年{m}月{d}日〜{end_match.group(4)}日" if end_match else f"{y}年{m}月{d}日"
        events.append({
            "title": title,
            "date": f"{y}-{int(m):02d}-{int(d):02d}",
            "date_display": date_display,
            "venue": "シーサイドスタジオCASO（大阪）",
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
    for h3 in soup.find_all("h3"):
        title_text = h3.get_text(strip=True)
        if not re.match(r"COMITIA\d+", title_text):
            continue
        block_text = ""
        for sib in h3.next_siblings:
            if getattr(sib, "name", None) == "h3":
                break
            if hasattr(sib, "get_text"):
                block_text += sib.get_text(separator=" ")
        date_match = re.search(r"日程[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日", block_text)
        if not date_match:
            continue
        y, m, d = date_match.groups()
        if not y.isdigit() or "x" in y.lower():
            continue
        venue_match = re.search(r"場所[：:]\s*([^\n　 ]+)", block_text)
        venue = venue_match.group(1).strip()[:40] if venue_match else "東京ビッグサイト"
        events.append({
            "title": title_text,
            "date": f"{y}-{int(m):02d}-{int(d):02d}",
            "date_display": f"{y}年{m}月{d}日",
            "venue": venue,
            "url": "https://www.comitia.co.jp/html/schedule.html",
            "category": "コミティア",
            "source": "comitia"
        })
    print(f"[コミティア] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 7. 関西コミティア
#    アプローチ変更: ページ全体テキストから
#    「関西コミティアXX」+日付のセットを正規表現で直接抽出
# ─────────────────────────────────────────────
def scrape_k_comitia():
    events = []
    soup = fetch("https://www.k-comitia.com/")
    if not soup:
        return events

    # ページ全体のテキストを取得
    full_text = soup.get_text(separator="\n")

    # デバッグ: 「関西コミティア」周辺のテキストを確認
    idx = full_text.find("関西コミティア76")
    if idx >= 0:
        print(f"[関西コミティア] DEBUG: ...{repr(full_text[idx:idx+200])}...")
    else:
        print("[関西コミティア] DEBUG: '関西コミティア76' がテキストに見つかりません")
        print(f"[関西コミティア] DEBUG: ページ先頭200文字: {repr(full_text[:200])}")

    # 「開催日程」セクション以降を対象にする
    schedule_idx = full_text.find("開催日程")
    if schedule_idx < 0:
        print("[関西コミティア] '開催日程' セクションが見つかりません")
        return events

    schedule_text = full_text[schedule_idx:]

    # 「関西コミティアXX\n...\n2026年M月D日」のブロックを繰り返し抽出
    # ブロック: 「関西コミティアXX」から次の「関西コミティア」まで
    blocks = re.split(r"(?=関西コミティア\d+)", schedule_text)

    for block in blocks:
        # タイトル行
        title_match = re.match(r"(関西コミティア\d+)", block)
        if not title_match:
            continue
        title = title_match.group(1)

        # 読書会・出張は除外
        if "読書会" in block[:30] or "出張" in block[:30]:
            continue

        # 日付
        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", block)
        if not date_match:
            continue
        y, m, d = date_match.groups()

        # 会場（「開催場所」の次の行）
        venue_match = re.search(r"開催場所\s*\n+([^\n]+)", block)
        venue = venue_match.group(1).strip()[:40] if venue_match else "インテックス大阪ほか"

        events.append({
            "title": title,
            "date": f"{y}-{int(m):02d}-{int(d):02d}",
            "date_display": f"{y}年{m}月{d}日",
            "venue": venue,
            "url": "https://www.k-comitia.com/",
            "category": "コミティア",
            "source": "k_comitia"
        })

    print(f"[関西コミティア] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 8. コミックマーケット
# ─────────────────────────────────────────────
def scrape_comiket():
    events = []
    raw = fetch_text("https://www.comiket.co.jp/", encoding="iso-2022-jp")
    if not raw:
        return events

    date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日[〜～](\d{1,2})日", raw)
    if not date_match:
        date_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw)
        if not date_match:
            print("[コミケ] 日程テキストが見つかりませんでした")
            return events
        y, m, d = date_match.groups()
        date_display = f"{y}年{m}月{d}日"
    else:
        y, m, d, d2 = date_match.groups()
        date_display = f"{y}年{m}月{d}日〜{d2}日"

    c_match = re.search(r"コミックマーケット\s*(\d{3})", raw)
    title = f"コミックマーケット{c_match.group(1)}" if c_match else "コミックマーケット"

    c_num_match = re.search(r"C(\d{3})Info", raw)
    info_url = f"https://www.comiket.co.jp/info-a/C{c_num_match.group(1)}/C{c_num_match.group(1)}Info.html" if c_num_match else "https://www.comiket.co.jp/"

    events.append({
        "title": title,
        "date": f"{y}-{int(m):02d}-{int(d):02d}",
        "date_display": date_display,
        "venue": "東京ビッグサイト",
        "url": info_url,
        "category": "コミックマーケット",
        "source": "comiket"
    })
    print(f"[コミックマーケット] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# 手動追加イベント
# ─────────────────────────────────────────────
def load_manual_events():
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
# ─────────────────────────────────────────────
# 技術書典
# ─────────────────────────────────────────────
def scrape_techbookfest():
    events = []
    soup = fetch("https://blog.techbookfest.org/")
    if not soup:
        return events

    text = soup.get_text(separator="\n")

    offline_match = re.search(
        r"(技術書典\d+)[\s\S]{0,50}?オフライン開催[\s\S]{0,100}?〈会期〉\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
        text
    )
    online_match = re.search(
        r"(技術書典\d+)[\s\S]{0,50}?オンライン開催[\s\S]{0,100}?〈会期〉\s*(\d{4})年(\d{1,2})月(\d{1,2})日[^\n]{0,20}[〜～](\d{1,2})月(\d{1,2})日",
        text
    )

    venue_match = re.search(r"〈会場〉([^\n]+)", text)
    venue = venue_match.group(1).strip()[:40] if venue_match else "池袋サンシャインシティ"

    url_match = re.search(r"https://techbookfest\.org/event/tbf\d+", text)
    url = url_match.group(0) if url_match else "https://techbookfest.org/"

    if offline_match:
        title = offline_match.group(1)
        y, m, d = offline_match.group(2), offline_match.group(3), offline_match.group(4)
        events.append({
            "title": f"{title}（オフライン）",
            "date": f"{y}-{int(m):02d}-{int(d):02d}",
            "date_display": f"{y}年{m}月{d}日",
            "venue": venue,
            "url": url,
            "category": "技術書典",
            "source": "techbookfest"
        })

    if online_match:
        title = online_match.group(1)
        y, m1, d1, m2, d2 = (
            online_match.group(2), online_match.group(3), online_match.group(4),
            online_match.group(5), online_match.group(6)
        )
        events.append({
            "title": f"{title}（オンライン）",
            "date": f"{y}-{int(m1):02d}-{int(d1):02d}",
            "date_display": f"{y}年{m1}月{d1}日〜{m2}月{d2}日",
            "venue": "技術書典オンラインマーケット",
            "url": url,
            "category": "技術書典",
            "source": "techbookfest"
        })

    print(f"[技術書典] {len(events)} events found")
    return events
# ─────────────────────────────────────────────
def scrape_techbookfest():
    events = []
    soup = fetch("https://blog.techbookfest.org/")
    if not soup:
        return events

    text = soup.get_text(separator="\n")

    # 「技術書典XX オフライン開催 〈会期〉2026年4月12日(日)」パターン
    offline_match = re.search(
        r"(技術書典\d+)[\s\S]{0,50}?オフライン開催[\s\S]{0,100}?〈会期〉\s*(\d{4})年(\d{1,2})月(\d{1,2})日",
        text
    )
    # 「技術書典XX オンライン開催 〈会期〉2026年4月11日(土) ～ 4月26日(日)」パターン
    online_match = re.search(
        r"(技術書典\d+)[\s\S]{0,50}?オンライン開催[\s\S]{0,100}?〈会期〉\s*(\d{4})年(\d{1,2})月(\d{1,2})日[^\n]{0,20}[〜～](\d{1,2})月(\d{1,2})日",
        text
    )

    # 会場（オフライン）
    venue_match = re.search(r"〈会場〉([^\n]+)", text)
    venue = venue_match.group(1).strip()[:40] if venue_match else "池袋サンシャインシティ"

    # イベントページURL
    url_match = re.search(r"https://techbookfest\.org/event/tbf\d+", text)
    url = url_match.group(0) if url_match else "https://techbookfest.org/"

    if offline_match:
        title = offline_match.group(1)
        y, m, d = offline_match.group(2), offline_match.group(3), offline_match.group(4)
        events.append({
            "title": f"{title}（オフライン）",
            "date": f"{y}-{int(m):02d}-{int(d):02d}",
            "date_display": f"{y}年{m}月{d}日",
            "venue": venue,
            "url": url,
            "category": "技術書典",
            "source": "techbookfest"
        })

    if online_match:
        title = online_match.group(1)
        y, m1, d1, m2, d2 = (
            online_match.group(2), online_match.group(3), online_match.group(4),
            online_match.group(5), online_match.group(6)
        )
        events.append({
            "title": f"{title}（オンライン）",
            "date": f"{y}-{int(m1):02d}-{int(d1):02d}",
            "date_display": f"{y}年{m1}月{d1}日〜{m2}月{d2}日",
            "venue": "技術書典オンラインマーケット",
            "url": url,
            "category": "技術書典",
            "source": "techbookfest"
        })

    print(f"[技術書典] {len(events)} events found")
    return events


# ─────────────────────────────────────────────
# GAS自動追加の文フリイベントを読み込む
# ─────────────────────────────────────────────
def load_bunfree_events():
    """GASが自動更新する docs/bunfree_events.json を読み込む"""
    path = "docs/bunfree_events.json"
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            events = json.load(f)
        print(f"[文フリ自動] {len(events)} events loaded")
        return events
    except Exception as e:
        print(f"[文フリ自動] 読み込みエラー: {e}")
        return []


# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def run_all():
    all_events = []
    all_events += scrape_tabf()
    all_events += scrape_mzfest()
    all_events += scrape_zinefes_note()
    all_events += scrape_artbookosaka()
    all_events += scrape_comitia()
    all_events += scrape_k_comitia()
    all_events += scrape_comiket()
    all_events += scrape_techbookfest()
    all_events += load_manual_events()   # 手動イベント（ZINEの商店街など）
    all_events += load_bunfree_events()  # GAS自動追加の文フリイベント

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
