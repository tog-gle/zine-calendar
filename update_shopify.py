"""
events.json から地域別のイベント一覧HTMLをつくり、
diybooks.jp の「全国のZINEイベント一覧」ページ本文の
  <div id="zine-list"></div>
の中身だけを書き換える。その外側（説明文など）には触らない。
見た目・入稿日チェック・代理表示はテーマのカスタムLiquid（zine-list.liquid）が担当する。

必要な GitHub Secrets
  SHOPIFY_SHOP           例: xxxxx.myshopify.com
  SHOPIFY_CLIENT_ID      Dev Dashboard のアプリの Client ID
  SHOPIFY_CLIENT_SECRET  同 Client secret
  （アプリの権限: read_online_store_pages, write_online_store_pages）

ローカル確認:  python update_shopify.py --preview  → preview.html を書き出すだけ
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from html import escape

import requests

PAGE_HANDLE = "zine-event-all"
API_VERSION = "2026-07"
# ページ本文の目印：<div id="zine-list"></div>（中身はこのスクリプトが毎回入れ替える）
MARK = re.compile(r'<div id="zine-list"[^>]*>.*?</div>', re.S)
JST = timezone(timedelta(hours=9))

# ─────────────────────────────────────────────
# 地域の振り分け
# ─────────────────────────────────────────────
REGIONS = [
    ("hokkaido-tohoku", "北海道・東北", "札幌・仙台ほか"),
    ("kanto", "関東", "東京・神奈川ほか"),
    ("chubu", "中部", "名古屋・静岡・北陸ほか"),
    ("kansai", "関西", "大阪・京都・神戸ほか"),
    ("chugoku-shikoku", "中国・四国", "広島・香川ほか"),
    ("kyushu-okinawa", "九州・沖縄", "福岡ほか"),
    ("other", "その他・オンライン", ""),
]

PLACES = {
    "hokkaido-tohoku": ["北海道", "札幌", "函館", "旭川", "青森", "岩手", "盛岡", "宮城", "仙台",
                        "秋田", "山形", "福島", "郡山", "いわき"],
    "kanto": ["東京", "吉祥寺", "池袋", "浜松町", "渋谷", "新宿", "下北沢", "高円寺", "神保町",
              "秋葉原", "有明", "ビッグサイト", "蔵前", "清澄白河", "神奈川", "横浜", "川崎", "鎌倉",
              "茅ヶ崎", "藤沢", "埼玉", "大宮", "千葉", "幕張", "茨城", "水戸", "つくば",
              "栃木", "宇都宮", "群馬", "前橋", "高崎"],
    "chubu": ["新潟", "富山", "石川", "金沢", "福井", "山梨", "甲府", "長野", "松本", "岐阜",
              "静岡", "浜松", "沼津", "愛知", "名古屋", "岡崎", "豊橋"],
    "kansai": ["大阪", "インテックス", "梅田", "難波", "堺", "京都", "長岡京", "みやこめっせ",
               "兵庫", "神戸", "三宮", "元町", "尼崎", "武庫之荘", "西宮", "芦屋", "姫路", "明石",
               "滋賀", "大津", "彦根", "奈良", "和歌山", "三重", "津市", "伊勢"],
    "chugoku-shikoku": ["鳥取", "島根", "松江", "岡山", "倉敷", "広島", "尾道", "山口", "下関",
                        "徳島", "香川", "高松", "愛媛", "松山", "高知"],
    "kyushu-okinawa": ["福岡", "博多", "北九州", "佐賀", "長崎", "熊本", "大分", "別府", "宮崎",
                       "鹿児島", "沖縄", "那覇"],
}


def region_of(ev):
    """会場→タイトルの順に地名を探し、いちばん手前に出てくる地名で決める
    （「東京都」の中の「京都」を拾わないように、出現位置の早いものを優先）"""
    for text in (ev.get("venue", ""), ev.get("title", "")):
        best = None
        for key, words in PLACES.items():
            for w in words:
                i = text.find(w)
                if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(w) > best[1])):
                    best = (i, len(w), key)
        if best:
            return best[2]
    return "other"


# ─────────────────────────────────────────────
# 地域別ページ（ページが無ければ自動で作成し、以後は一覧部分だけ更新）
# 導入文は作成時だけ入る。あとはShopifyの編集画面で自由に直してOK
# ─────────────────────────────────────────────
REGION_PAGES = {
    "hokkaido-tohoku": ("北海道・東北",
        "札幌や仙台をはじめ、北海道・東北で開かれるZINEフェスなど、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
    "kanto": ("東京・関東",
        "東京・神奈川をはじめ関東で開かれるZINEフェス東京、文学フリマ東京、コミティアなど、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
    "chubu": ("名古屋・中部",
        "名古屋・静岡・長野・北陸など中部で開かれるZINEフェスなど、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
    "kansai": ("大阪・関西",
        "大阪・京都・神戸をはじめ関西で開かれるZINEフェス大阪、まちのZINEフェス、文学フリマ京都、関西コミティアなど、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
    "chugoku-shikoku": ("広島・中国・四国",
        "広島・山口・香川・愛媛・高知など中国・四国で開かれるZINEフェスなど、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
    "kyushu-okinawa": ("福岡・九州・沖縄",
        "福岡・熊本・鹿児島・沖縄など九州・沖縄で開かれるZINEフェス、文学フリマ福岡など、ZINEや同人誌を出展・購入できるイベントの日程をまとめています。"),
}


def region_handle(key):
    return f"{PAGE_HANDLE}-{key}"


# ─────────────────────────────────────────────
# HTML生成
# ─────────────────────────────────────────────



def build_html(events, today):
    upcoming = [e for e in events if e.get("date") and e["date"] >= today.strftime("%Y-%m-%d")]
    upcoming.sort(key=lambda e: (e["date"], e["title"]))

    groups = {key: [] for key, _, _ in REGIONS}
    for e in upcoming:
        groups[region_of(e)].append(e)

    tabs, sections = [], []
    for key, name, examples in REGIONS:
        items = groups[key]
        if not items:
            continue
        tabs.append(f'<li><a href="#zl-{key}">{escape(name)}（{len(items)}）</a></li>')
        heading = f"{name}のZINEイベント・スケジュール"
        if examples:
            heading = f"{name}（{examples}）のZINEイベント・スケジュール"
        lis = [event_li(e) for e in items]
        sections.append(
            f'<section class="zl-region zl-by-region" id="zl-{key}">'
            f"<h2>{escape(heading)}</h2>"
            f'<ul class="zl-list">{"".join(lis)}</ul>'
            + (f'<p class="zl-more"><a href="/pages/{region_handle(key)}">{escape(REGION_PAGES[key][0])}のZINEイベントだけを見る →</a></p>'
               if key in REGION_PAGES else "")
            + "</section>"
        )

    updated = today.strftime("%Y年%-m月%-d日")
    return (
        '<div id="zine-list">'
        + region_nav(events, today)
        + "".join(sections)
        + f'<p class="zl-note"><time datetime="{today.strftime("%Y-%m-%dT%H:%M:%S+09:00")}">{updated}</time>時点の情報です。'
        '開催内容は各公式サイトでご確認ください。</p>'
        '</div>'
    )


def region_nav(events, today, current=None):
    t = today.strftime("%Y-%m-%d")
    counts = {}
    total = 0
    for e in events:
        if e.get("date") and e["date"] >= t:
            total += 1
            counts[region_of(e)] = counts.get(region_of(e), 0) + 1

    def item(href, label, n, on):
        cur = ' aria-current="page"' if on else ""
        return f'<li><a href="{href}"{cur}>{escape(label)}（{n}）</a></li>'

    items = [item(f"/pages/{PAGE_HANDLE}", "全国", total, current is None)]
    for key, name, _ in REGIONS:
        if key in REGION_PAGES and counts.get(key):
            items.append(item(f"/pages/{region_handle(key)}", name, counts[key], current == key))
    return f'<ul class="zl-tabs zl-regions">{"".join(items)}</ul>'


def event_li(e):
    title = escape(e["title"])
    link = (f'<a href="{escape(e["url"])}" target="_blank" rel="noopener">{title}</a>'
            if e.get("url") else title)
    meta = escape(e.get("date_display") or e["date"])
    if e.get("venue"):
        meta += "｜" + escape(e["venue"])
    cat = f'<span class="zl-cat">{escape(e["category"])}</span>' if e.get("category") else ""
    return f'<li><h3>{link}</h3>{cat}<p><time datetime="{e["date"]}">{meta}</time></p></li>'


def build_region_html(events, today, key):
    """地域別ページの一覧部分。見出しは月ごと（h2）、イベントはh3"""
    upcoming = sorted(
        [e for e in events if e.get("date") and e["date"] >= today.strftime("%Y-%m-%d") and region_of(e) == key],
        key=lambda e: (e["date"], e["title"]))
    months = {}
    for e in upcoming:
        months.setdefault(e["date"][:7], []).append(e)

    label = REGION_PAGES[key][0]
    tabs = "".join(f'<li><a href="#zl-{ym}">{int(ym[5:])}月</a></li>' for ym in months)
    sections = "".join(
        f'<section class="zl-region" id="zl-{ym}"><h2>{int(ym[:4])}年{int(ym[5:])}月の{escape(label)}のZINEイベント</h2>'
        f'<ul class="zl-list">{"".join(event_li(e) for e in items)}</ul></section>'
        for ym, items in months.items())
    if not sections:
        sections = '<p>現在、予定されているイベントはありません。</p>'

    others = "".join(
        f'<li><a href="/pages/{region_handle(k)}">{escape(v[0])}</a></li>'
        for k, v in REGION_PAGES.items() if k != key)
    updated = today.strftime("%Y年%-m月%-d日")
    return (
        '<div id="zine-list">'
        + region_nav(events, today, key)
        + (f'<ul class="zl-tabs zl-months">{tabs}</ul>' if tabs else "")
        + sections
        + f'<p class="zl-note"><time datetime="{today.strftime("%Y-%m-%dT%H:%M:%S+09:00")}">{updated}</time>時点の情報です。'
        '開催内容は各公式サイトでご確認ください。</p>'
        f'<h2>ほかの地域のZINEイベント</h2><ul class="zl-others">{others}'
        f'<li><a href="/pages/{PAGE_HANDLE}">全国のZINEイベント一覧</a></li></ul>'
        '</div>'
    )


def region_years(events, today, key):
    ys = sorted({e["date"][:4] for e in events
                 if e.get("date") and e["date"] >= today.strftime("%Y-%m-%d") and region_of(e) == key})
    if not ys:
        return today.strftime("%Y")
    return ys[0] if len(ys) == 1 else f"{ys[0]}–{ys[-1]}"


# ─────────────────────────────────────────────
# Shopify
# ─────────────────────────────────────────────
def get_token(shop, cid, secret):
    res = requests.post(
        f"https://{shop}/admin/oauth/access_token",
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
        timeout=20,
    )
    if res.status_code != 200:
        raise RuntimeError(f"トークン取得に失敗 {res.status_code}: {res.text[:300]}")
    data = res.json()
    scopes = data.get("scope", "")
    print(f"[Shopify] 許可されている権限: {scopes or '（なし）'}")
    if "write_online_store_pages" not in scopes:
        raise RuntimeError("write_online_store_pages が許可されていません。アプリをストアに入れ直して権限を承認してください")
    return data["access_token"]


def gql(shop, token, query, variables=None):
    res = requests.post(
        f"https://{shop}/admin/api/{API_VERSION}/graphql.json",
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    if res.status_code != 200:
        raise RuntimeError(f"API呼び出しに失敗 {res.status_code}: {res.text[:300]}")
    data = res.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


PAGE_QUERY = 'query($q:String!){pages(first:1,query:$q){nodes{id handle title body templateSuffix}}}'
UPDATE = ('mutation($id:ID!,$page:PageUpdateInput!){pageUpdate(id:$id,page:$page)'
          '{page{id}userErrors{field message}}}')
CREATE = ('mutation($page:PageCreateInput!){pageCreate(page:$page)'
          '{page{id handle}userErrors{field message}}}')


def find_page(shop, token, handle):
    nodes = gql(shop, token, PAGE_QUERY, {"q": f"handle:{handle}"})["pages"]["nodes"]
    return next((n for n in nodes if n["handle"] == handle), None)


def check(res, key):
    errs = res[key]["userErrors"]
    if errs:
        raise RuntimeError(errs)


def main():
    with open("docs/events.json", encoding="utf-8") as f:
        events = json.load(f)["events"]
    today = datetime.now(JST)
    block = build_html(events, today)

    if "--preview" in sys.argv:
        wrap = '<meta charset="utf-8"><div style="max-width:720px;margin:auto;font-family:sans-serif">{}</div>'
        with open("preview.html", "w", encoding="utf-8") as f:
            f.write(wrap.format(block))
        with open("preview-kanto.html", "w", encoding="utf-8") as f:
            f.write(wrap.format(build_region_html(events, today, "kanto")))
        print("preview.html / preview-kanto.html を書き出しました")
        return

    shop = (os.environ.get("SHOPIFY_SHOP") or "").strip()
    shop = re.sub(r"^https?://", "", shop).strip("/")
    cid = os.environ.get("SHOPIFY_CLIENT_ID")
    secret = os.environ.get("SHOPIFY_CLIENT_SECRET")
    if not (shop and cid and secret):
        print("[Shopify] Secrets が未設定のためスキップ")
        return

    token = get_token(shop, cid, secret)

    # 1. 全国ページ
    page = find_page(shop, token, PAGE_HANDLE)
    if not page:
        raise RuntimeError(f"ページ {PAGE_HANDLE} が見つかりません")
    body = page["body"] or ""
    if not MARK.search(body):
        raise RuntimeError('ページ本文に <div id="zine-list"></div> がありません。HTML表示で本文に追加してください')
    check(gql(shop, token, UPDATE, {"id": page["id"], "page": {"body": MARK.sub(lambda m: block, body, count=1)}}),
          "pageUpdate")
    print(f"[Shopify] {PAGE_HANDLE} を更新しました")

    # 2. 地域別ページ（全国ページと同じテンプレートを使う＝入稿日チェックも付く）
    template = page.get("templateSuffix") or ""
    failed = []
    for key, (label, intro) in REGION_PAGES.items():
        handle = region_handle(key)
        title = f"{label}のZINEイベント・スケジュール {region_years(events, today, key)}"
        rblock = build_region_html(events, today, key)
        try:
            rp = find_page(shop, token, handle)
            if rp is None:
                new_body = (f"<p>{escape(intro)}週に2回、自動で更新しています。</p>"
                            f"<p>出たいイベントにチェックを入れると、印刷の入稿日の目安が分かります。</p>{rblock}")
                page_input = {"title": title, "handle": handle, "body": new_body, "isPublished": True}
                if template:
                    page_input["templateSuffix"] = template
                check(gql(shop, token, CREATE, {"page": page_input}), "pageCreate")
                print(f"[Shopify] {handle} を作成しました")
            else:
                rbody = rp["body"] or ""
                rbody = MARK.sub(lambda m: rblock, rbody, count=1) if MARK.search(rbody) else rbody + rblock
                check(gql(shop, token, UPDATE, {"id": rp["id"], "page": {"title": title, "body": rbody}}),
                      "pageUpdate")
                print(f"[Shopify] {handle} を更新しました")
        except Exception as err:
            print(f"[Shopify] {handle} でエラー: {err}")
            failed.append(handle)
    if failed:
        raise RuntimeError(f"地域別ページの一部が失敗: {', '.join(failed)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"[Shopify] エラー: {err}")
        sys.exit(1)
