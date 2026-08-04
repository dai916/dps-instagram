#!/usr/bin/env python3
"""
refresh_token.py — IG 長期アクセストークンの自動更新
=================================================
長期トークンは約60日で失効。Threads/IG共通の論点。
本スクリプトを token-refresh.yml で定期実行（例: 週1）し、更新後の値を
GitHub Secrets API で IG_ACCESS_TOKEN に書き戻す。

Facebook長期ユーザートークンの更新エンドポイント:
  GET /oauth/access_token?grant_type=fb_exchange_token
      &client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=CURRENT

GitHub Secrets への書き戻しには libsodium 暗号化が必要。
ここでは更新後トークンを stdout(JSON) に出し、ワークフロー側で
`gh secret set` するか、GH_PAT を使って Secrets API を叩く。

必須環境変数: META_APP_ID, META_APP_SECRET, IG_ACCESS_TOKEN
任意: GH_PAT, GH_REPO（指定時は Secrets API へ自動書き戻し）
"""
import base64
import json
import os
import sys

import requests

GRAPH = "https://graph.facebook.com/v21.0"


def refresh():
    app_id = os.environ["META_APP_ID"]
    app_secret = os.environ["META_APP_SECRET"]
    current = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get(f"{GRAPH}/oauth/access_token", params={
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": current,
    }, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["access_token"], data.get("expires_in")


def write_github_secret(repo, pat, name, value):
    """GitHub Secrets API へ libsodium 暗号化して書き戻す。"""
    from nacl import encoding, public  # pip install pynacl
    h = {"Authorization": f"Bearer {pat}",
         "Accept": "application/vnd.github+json"}
    key = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=h, timeout=30).json()
    pk = public.PublicKey(key["key"].encode(), encoding.Base64Encoder())
    sealed = public.SealedBox(pk).encrypt(value.encode())
    enc = base64.b64encode(sealed).decode()
    resp = requests.put(
        f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
        headers=h, timeout=30,
        json={"encrypted_value": enc, "key_id": key["key_id"]})
    resp.raise_for_status()


def main():
    token, expires_in = refresh()
    repo = os.environ.get("GH_REPO")
    pat = os.environ.get("GH_PAT")
    if repo and pat:
        write_github_secret(repo, pat, "IG_ACCESS_TOKEN", token)
        print(json.dumps({"refreshed": True, "expires_in": expires_in,
                          "written_to_secret": True}))
    else:
        # ワークフロー側で gh secret set する想定。マスクして出力。
        print(f"::add-mask::{token}")
        print(json.dumps({"refreshed": True, "expires_in": expires_in,
                          "token": token}))


if __name__ == "__main__":
    main()
