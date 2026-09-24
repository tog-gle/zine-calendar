"""
events.json から地域別のイベント一覧HTMLをつくり、
diybooks.jp の「全国のZINEイベント一覧」ページ本文の
  <!-- ZINE-LIST:START --> 〜 <!-- ZINE-LIST:END -->
の間だけを書き換える。目印の外側（説明文・埋め込みなど）には触らない。

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
START = "<!-- ZINE-LIST:START -->"
END = "<!-- ZINE-LIST:END -->"
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
# HTML生成
# ─────────────────────────────────────────────
STYLE = """<style>
.zl-tabs{display:flex;flex-wrap:wrap;gap:.4rem;margin:1.5rem 0 1rem;padding:0;list-style:none}
.zl-tabs a{display:inline-block;padding:.35rem .8rem;border:1px solid currentColor;border-radius:999px;font-size:.85rem;text-decoration:none}
.zl-region{margin-top:2rem;scroll-margin-top:5rem}
.zl-region h2{font-size:1.2rem;border-bottom:2px solid currentColor;padding-bottom:.3rem}
.zl-list{list-style:none;padding:0;margin:0}
.zl-list li{padding:.7rem 0;border-bottom:1px solid rgba(0,0,0,.12)}
.zl-list h3{font-size:1rem;margin:0 0 .2rem}
.zl-list p{font-size:.85rem;margin:0;opacity:.8}
.zl-note{font-size:.75rem;opacity:.7;margin-top:1rem}
</style>"""


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
        lis = []
        for e in items:
            title = escape(e["title"])
            link = (f'<a href="{escape(e["url"])}" target="_blank" rel="noopener">{title}</a>'
                    if e.get("url") else title)
            meta = escape(e.get("date_display") or e["date"])
            if e.get("venue"):
                meta += "｜" + escape(e["venue"])
            lis.append(f"<li><h3>{link}</h3><p>{meta}</p></li>")
        sections.append(
            f'<section class="zl-region" id="zl-{key}">'
            f"<h2>{escape(heading)}</h2>"
            f'<ul class="zl-list">{"".join(lis)}</ul></section>'
        )

    updated = today.strftime("%Y年%-m月%-d日")
    return (
        f"{START}\n{STYLE}\n"
        f'<ul class="zl-tabs">{"".join(tabs)}</ul>\n'
        + "\n".join(sections)
        + f'\n<p class="zl-note">{updated}時点の情報です。開催内容は各公式サイトでご確認ください。</p>\n{END}'
    )


# ─────────────────────────────────────────────
# Shopify
# ─────────────────────────────────────────────
def get_token(shop, cid, secret):
    res = requests.post(
        f"https://{shop}/admin/oauth/access_token",
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": secret},
        timeout=20,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def gql(shop, token, query, variables=None):
    res = requests.post(
        f"https://{shop}/admin/api/{API_VERSION}/graphql.json",
        headers={"X-Shopify-Access-Token": token, "Content-Type": "application/json"},
        json={"query": query, "variables": variables or {}},
        timeout=30,
    )
    res.raise_for_status()
    data = res.json()
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def main():
    with open("docs/events.json", encoding="utf-8") as f:
        events = json.load(f)["events"]
    today = datetime.now(JST)
    block = build_html(events, today)

    if "--preview" in sys.argv:
        with open("preview.html", "w", encoding="utf-8") as f:
            f.write(f'<meta charset="utf-8"><div style="max-width:720px;margin:auto;font-family:sans-serif">{block}</div>')
        print("preview.html を書き出しました")
        return

    shop = os.environ.get("SHOPIFY_SHOP")
    cid = os.environ.get("SHOPIFY_CLIENT_ID")
    secret = os.environ.get("SHOPIFY_CLIENT_SECRET")
    if not (shop and cid and secret):
        print("[Shopify] Secrets が未設定のためスキップ")
        return

    token = get_token(shop, cid, secret)
    data = gql(shop, token,
               'query($q:String!){pages(first:1,query:$q){nodes{id handle body}}}',
               {"q": f"handle:{PAGE_HANDLE}"})
    nodes = data["pages"]["nodes"]
    if not nodes:
        raise RuntimeError(f"ページ {PAGE_HANDLE} が見つかりません")
    page = nodes[0]
    body = page["body"] or ""

    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(body):
        raise RuntimeError("ページ本文に目印（ZINE-LIST:START / END）がありません。先に本文へ追加してください")
    new_body = pattern.sub(lambda m: block, body, count=1)

    if new_body == body:
        print("[Shopify] 変更なし")
        return

    res = gql(shop, token,
              'mutation($id:ID!,$page:PageUpdateInput!){pageUpdate(id:$id,page:$page){page{id}userErrors{field message}}}',
              {"id": page["id"], "page": {"body": new_body}})
    errs = res["pageUpdate"]["userErrors"]
    if errs:
        raise RuntimeError(errs)
    print(f"[Shopify] {PAGE_HANDLE} を更新しました")


if __name__ == "__main__":
    main()
