# dps-instagram — DPSリール自動投稿

デンタルプリンティングサービス（@dental_printing_service）のInstagramリールを、
2日に1回 19:00 JST に自動投稿するリポジトリ。iconnect-instagramの構成を流用。

## 仕組み
- `docs/` を GitHub Pages で公開（`media/R01.mp4`〜`R16.mp4` と `covers/R01.png`〜）
- `post.yml` が毎日 10:00 UTC（19:00 JST）に起動し、`schedule.json` に当日日付の
  エントリがあれば Instagram Graph API（FBページ連携型）でリール投稿
- 投稿済みは `posted.json` に記録して重複防止
- `token-refresh.yml` が週次で長期トークンを更新し Secrets に書き戻し

## スケジュール
2026-08-05（R01）〜 2026-09-04（R16）、2日おき19:00 JST。詳細は `schedule.json`。
※ GitHub Actions の cron は数分〜30分遅延することがある（19:00〜19:30目安）。

## 必要な GitHub Secrets
| Secret | 内容 |
|---|---|
| `IG_USER_ID` | DPSのIGビジネスアカウントID |
| `IG_ACCESS_TOKEN` | 長期アクセストークン（60日・自動更新） |
| `META_APP_ID` / `META_APP_SECRET` | Metaアプリ（iconnectと共用） |
| `GH_PAT` | トークン書き戻し用 fine-grained PAT（このrepoのSecrets: Read and write） |

## 手動操作
```bash
# 疎通テスト（公開しない）
gh workflow run post.yml -f id=R01 -f validate=true
# 取りこぼし復旧（指定IDを即時投稿）
gh workflow run post.yml -f id=R01
```

## コンプライアンス
投稿直前に `post_reel.py` のNGゲートが作動（料金額・優良性ワード検出で中止）。
キャプション末尾に「＊歯科医師、歯科医院対象」必須。

## 素材の原本
`/Users/tomitadaisuke/Claude/Projects/DPSインスタグラム投稿/リール/`（render_reel.pyで再生成可）。
動画を差し替えたら `docs/media/RNN.mp4` を上書きしてpush（Pages反映に数分）。
