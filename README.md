# ZINE Calendar - セットアップガイド

DIY BOOKS向け ZINEイベントカレンダー自動更新システム

## ファイル構成

```
zine-calendar/
├── scraper.py                      # スクレイピング本体
├── sync_to_shopify.py              # Shopify同期
├── page.zine-calendar.liquid       # Shopifyテンプレート
├── .github/
│   └── workflows/
│       └── weekly.yml              # GitHub Actions（週2回自動実行）
└── README.md
```

---

## STEP 1: GitHubリポジトリを作る

1. https://github.com/new にアクセス
2. リポジトリ名: `zine-calendar`（プライベートでOK）
3. このフォルダの中身をまるごとpush

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/あなたのユーザー名/zine-calendar.git
git push -u origin main
```

---

## STEP 2: Shopify Admin APIトークンを取得

1. Shopify管理画面 → **設定** → **アプリと販売チャネル**
2. 右上の **「アプリを開発する」** をクリック
3. 「カスタムアプリを作成する」
4. アプリ名: `ZINE Calendar Sync`（なんでもOK）
5. **「Admin APIの権限を設定する」** で以下を選択:
   - `read_metafields` ✅
   - `write_metafields` ✅
6. 「保存」→「APIの認証情報」タブ →「アクセストークンを表示」
7. **shpat_xxxxxxxxxx** の形式のトークンをコピー（一度しか表示されないので注意！）

---

## STEP 3: GitHub Secrets を設定

1. GitHubリポジトリ → **Settings** → **Secrets and variables** → **Actions**
2. 「New repository secret」で2つ追加:

| Secret名 | 値 |
|----------|---|
| `SHOPIFY_STORE` | `diybooks.myshopify.com` |
| `SHOPIFY_TOKEN` | `shpat_xxxxxxxxxx`（STEP2で取得） |

---

## STEP 4: 動作確認（手動実行）

1. GitHubリポジトリ → **Actions** タブ
2. 「ZINE Calendar Sync」→ 「Run workflow」
3. ✅ が出ればOK

---

## STEP 5: Shopifyにカレンダーページを作る

### 5-1. Liquidテンプレートを追加

1. Shopify管理画面 → **オンラインストア** → **テーマ** → 「コードを編集」
2. `templates` フォルダ → 「新しいテンプレートを追加」
3. 種類: `page`、名前: `zine-calendar`
4. `page.zine-calendar.liquid` の内容をそのまま貼り付けて保存

### 5-2. ページを作成

1. Shopify管理画面 → **オンラインストア** → **ページ** → 「ページを追加」
2. タイトル: `ZINEイベントカレンダー`
3. テンプレート: `page.zine-calendar`（右側のプルダウンで選択）
4. 保存 → URLに追加してサイトに掲載

---

## 自動実行のスケジュール

`weekly.yml` の設定:
- **毎週月曜・木曜 朝9時（JST）** に自動実行
- GitHubのActionsタブからいつでも手動実行も可能

変更したい場合は `.github/workflows/weekly.yml` の `cron` 行を編集:
```yaml
# 毎日朝9時に変更する例
- cron: "0 0 * * *"
```

---

## スクレイピング対象

| サイト | URL | 取得内容 |
|--------|-----|---------|
| Tokyo Art Book Fair | tokyoartbookfair.com | 年1回の大型イベント情報 |
| 文学フリマ | bunfree.net | 各地の開催情報 |
| まちのZINEフェス | mzfest.3zui.jp | 関西中心のZINEイベント |
| ZINEフェス一覧 | note.com/bookcultureclub | 全国ZINEフェス日程 |

### 新しいサイトを追加したい場合

`scraper.py` に新しい関数を追加して `run_all()` に呼び出しを追加するだけ:

```python
def scrape_new_site():
    events = []
    soup = fetch("https://example.com/events")
    # ... 取得ロジック
    return events

def run_all():
    all_events = []
    all_events += scrape_tabf()
    all_events += scrape_bunfree()
    all_events += scrape_mzfest()
    all_events += scrape_zinefes_note()
    all_events += scrape_new_site()  # ← 追加
    ...
```

---

## トラブルシューティング

**GitHub Actionsが失敗する場合**
→ ActionsタブのログでエラーメッセージとSTEPを確認

**Shopifyにデータが反映されない場合**
→ SHOPIFY_STORE が `diybooks.myshopify.com`（末尾スラッシュなし）になっているか確認
→ SHOPIFY_TOKEN の権限に `write_metafields` が含まれているか確認

**特定サイトが取得できない場合**
→ `scraper.py` を手元で `python scraper.py` 実行してログを確認
→ サイトのHTML構造が変わっている可能性があるため、セレクタを更新
