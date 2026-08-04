#!/usr/bin/env python3
"""
post_reel.py — DPS リールを Instagram Graph API で自動投稿
==========================================================
iconnect-instagram の post_to_instagram.py を流用した簡易版。

- schedule.json から当日(JST)のエントリを探して投稿する
- 投稿済みは posted.json に記録（重複投稿防止。ワークフローがcommitする）
- メディアは GitHub Pages の公開URL（MEDIA_BASE + video/cover パス）
- FBページ連携型 Instagram Graph API（REELS コンテナ → media_publish）

必須環境変数: IG_USER_ID, IG_ACCESS_TOKEN, MEDIA_BASE
  MEDIA_BASE 例: https://dai916.github.io/dps-instagram

使い方:
  python scripts/post_reel.py                # 当日分を投稿
  python scripts/post_reel.py --id R01       # 指定IDを投稿（復旧用）
  python scripts/post_reel.py --id R01 --validate  # コンテナ作成のみ（公開しない疎通テスト）
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

import requests

GRAPH = "https://graph.facebook.com/v21.0"
IG_USER_ID = os.environ.get("IG_USER_ID", "")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
MEDIA_BASE = os.environ.get("MEDIA_BASE", "").rstrip("/")
SCHEDULE = "schedule.json"
POSTED = "posted.json"

# 厚労省 歯科技工広告ガイドライン対応の投稿直前ゲート（最後の安全網）
NG_WORDS = ["最高", "日本一", "低価格", "格安", "激安", "短納期", "高品質",
            "No.1", "ナンバーワン", "どこよりも"]
import re
PRICE_RE = re.compile(r"[0-9,０-９]+\s*円|¥\s*[0-9,]+")


def guard(text):
    hits = [w for w in NG_WORDS if w in text]
    if PRICE_RE.search(text):
        hits.append("具体的金額")
    if hits:
        raise RuntimeError(f"投稿中止: NGゲート検出 {hits}")


def _post(url, params, tries=5):
    delay = 2
    last = None
    for _ in range(tries):
        r = requests.post(url, data=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        last = r.text
        try:
            code = r.json().get("error", {}).get("code")
        except Exception:
            code = None
        if code in (1, 2, 4, 17, 24, 32, 613):
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
        break
    raise RuntimeError(f"API失敗: {last}")


def _wait_finished(container_id, tries=30):
    delay = 5
    for _ in range(tries):
        r = requests.get(f"{GRAPH}/{container_id}",
                         params={"fields": "status_code", "access_token": TOKEN},
                         timeout=60)
        st = r.json().get("status_code")
        if st == "FINISHED":
            return True
        if st == "ERROR":
            raise RuntimeError(f"コンテナ処理エラー: {r.text}")
        time.sleep(delay)
        delay = min(delay + 3, 20)
    raise RuntimeError("コンテナがFINISHEDになりませんでした")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def pick_entry(args, schedule, posted_ids):
    if args.id:
        for e in schedule:
            if e["id"] == args.id:
                return e
        sys.exit(f"schedule.json に {args.id} がありません")
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
    for e in schedule:
        if e["date"] == today:
            if e["id"] in posted_ids:
                print(f"{e['id']} は投稿済み。スキップ")
                sys.exit(0)
            return e
    print(f"本日({today})の予定はありません")
    sys.exit(0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", help="投稿するリールID（省略時は当日分）")
    ap.add_argument("--validate", action="store_true",
                    help="コンテナ作成＋処理完了確認のみ。公開はしない（疎通テスト）")
    args = ap.parse_args()

    if not (IG_USER_ID and TOKEN and MEDIA_BASE):
        sys.exit("環境変数 IG_USER_ID / IG_ACCESS_TOKEN / MEDIA_BASE が必要")

    schedule = load_json(SCHEDULE, [])
    posted = load_json(POSTED, [])
    posted_ids = {p["id"] for p in posted}

    entry = pick_entry(args, schedule, posted_ids)
    if not args.validate and entry["id"] in posted_ids:
        sys.exit(f"{entry['id']} は投稿済みです（--id指定でも重複投稿はしない）")

    caption = entry["caption"]
    guard(caption)

    video_url = f"{MEDIA_BASE}/{entry['video']}"
    cover_url = f"{MEDIA_BASE}/{entry['cover']}"
    params = {"media_type": "REELS", "video_url": video_url,
              "caption": caption, "cover_url": cover_url,
              "share_to_feed": "true", "access_token": TOKEN}
    cid = _post(f"{GRAPH}/{IG_USER_ID}/media", params)["id"]
    _wait_finished(cid)

    if args.validate:
        print(json.dumps({"validated": True, "container": cid,
                          "id": entry["id"], "video_url": video_url},
                         ensure_ascii=False))
        return

    result = _post(f"{GRAPH}/{IG_USER_ID}/media_publish",
                   {"creation_id": cid, "access_token": TOKEN})

    posted.append({"id": entry["id"], "date": entry["date"],
                   "posted_at": dt.datetime.utcnow().isoformat() + "Z",
                   "media_id": result.get("id")})
    with open(POSTED, "w", encoding="utf-8") as f:
        json.dump(posted, f, ensure_ascii=False, indent=2)

    print(json.dumps({"published": result, "id": entry["id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
