"""
Shopify Metafield Sync
events.json の内容を Shopify の shop metafield に保存する
"""

import json
import os
import requests
import sys

# ─────────────────────────────────────────────
# 環境変数から認証情報を取得（GitHub Secrets に設定）
# ─────────────────────────────────────────────
SHOPIFY_STORE   = os.environ.get("SHOPIFY_STORE", "")    # 例: diybooks.myshopify.com
SHOPIFY_TOKEN   = os.environ.get("SHOPIFY_TOKEN", "")    # Admin API アクセストークン
NAMESPACE       = "zine_events"
KEY             = "calendar"
API_VERSION     = "2024-01"


def get_existing_metafield_id():
    """既存のmetafieldのIDを取得（update用）"""
    url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/metafields.json"
    params = {"namespace": NAMESPACE, "key": KEY, "owner_resource": "shop"}
    res = requests.get(url, headers=auth_headers(), params=params, timeout=15)
    res.raise_for_status()
    data = res.json()
    metafields = data.get("metafields", [])
    return metafields[0]["id"] if metafields else None


def auth_headers():
    return {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json"
    }


def sync_to_shopify(events_data: dict):
    """events.json の内容を Shopify に保存"""

    # 既存IDがあればPUT（更新）、なければPOST（新規）
    existing_id = get_existing_metafield_id()

    payload = {
        "metafield": {
            "namespace": NAMESPACE,
            "key": KEY,
            "value": json.dumps(events_data, ensure_ascii=False),
            "type": "json"
        }
    }

    if existing_id:
        # 更新
        url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/metafields/{existing_id}.json"
        res = requests.put(url, headers=auth_headers(), json=payload, timeout=15)
        action = "更新"
    else:
        # 新規作成
        url = f"https://{SHOPIFY_STORE}/admin/api/{API_VERSION}/metafields.json"
        res = requests.post(url, headers=auth_headers(), json=payload, timeout=15)
        action = "新規作成"

    if res.status_code in (200, 201):
        print(f"✅ Shopify metafield {action}成功")
        print(f"   イベント数: {events_data.get('count', '?')}件")
        print(f"   更新日時: {events_data.get('updated_at', '?')}")
    else:
        print(f"❌ Shopify API エラー: {res.status_code}")
        print(res.text)
        sys.exit(1)


def main():
    # 認証情報チェック
    if not SHOPIFY_STORE or not SHOPIFY_TOKEN:
        print("❌ 環境変数 SHOPIFY_STORE / SHOPIFY_TOKEN が未設定です")
        sys.exit(1)

    # events.json を読み込む
    try:
        with open("events.json", "r", encoding="utf-8") as f:
            events_data = json.load(f)
    except FileNotFoundError:
        print("❌ events.json が見つかりません。先に scraper.py を実行してください")
        sys.exit(1)

    print(f"📦 {events_data.get('count', 0)}件のイベントをShopifyに送信します...")
    sync_to_shopify(events_data)


if __name__ == "__main__":
    main()
