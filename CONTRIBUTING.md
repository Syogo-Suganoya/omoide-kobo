# 開発ガイド

オモイデ工房を触るときの手引きです。使い方の概要は [README](README.md) を見てください。

## 開発環境

Docker だけあれば動きます。ローカルに Python も Node も要りません。

```bash
docker compose up --build
```

| サービス | ポート | 中身 |
|---|---|---|
| `api` | 8080 | FastAPI（`--reload`。`backend/` をマウントしているので保存で再起動） |
| `web` | 5173 | Vite dev server（HMR。`/api` は `api` へプロキシ） |
| `firestore` | 8085 | Firestore エミュレータ（`api` はこれが立ち上がるのを待って起動） |
| `docs` | — | アーキテクチャ図の生成（`--profile docs` のときだけ） |

## データの置き場

アルバム・写真のメタ情報・物語・旅程・共有リンク・監査ログは、**すべて Firestore** に入ります。
開発ではエミュレータ（`firestore` サービス）、本番では GCP の Firestore を同じコードで使います。
切り替えは `FIRESTORE_EMULATOR_HOST` の有無だけで、アプリ側のコードは変わりません。

写真と音声の実体は Firestore ではなくオブジェクトストレージです（開発はボリューム `omoide-data` の
`/data/storage`、本番は Cloud Storage）。Firestore が持つのは、その参照（`family/{familyId}/…`）だけです。

**エミュレータのデータはメモリ上にあるので、`docker compose down` すると消えます。**
毎回まっさらから始めたいときはこれが好都合ですが、残したい場合は本物の Firestore に繋いでください。

| ドライバ | いつ使うか |
|---|---|
| `firestore`（既定） | 開発・本番。開発ではエミュレータを指す |
| `memory` | 自動テストのみ。プロセス内に持つだけの簡易実装 |

### モックと live の切り替え

初期状態は外部 API がすべて `mock` で、鍵なしで最後まで動きます。実 API に替えるときだけ `.env` を作ります。

```bash
cp .env.example .env      # GEMINI_MODE=live など、必要な行だけ live にする
WITH_LIVE_DEPS=true docker compose build api   # google-adk などを追加インストール
docker compose up
```

`google-adk` を含む GCP 系の依存は [requirements-live.txt](backend/requirements-live.txt) に分けてあります。
mock 運用では import されないので、開発イメージは軽いままです（この分離をやめると初回ビルドが 20 分以上かかります）。

## テスト

```bash
docker compose run --rm api pytest          # バックエンド（エミュレータも一緒に起動する）
docker compose exec web npm run build       # フロントの型検査（tsc -b）
```

テスト本体は `memory` ドライバで動かします（速くて、実行順に依存しないため）。
`FirestoreStore` の実コードだけは `test_firestore_store.py` がエミュレータ相手に踏みます。
エミュレータがいない環境では、このファイルは自動で skip されます。

テストはパイプラインの回帰だけでなく、**設計書 7 章のガバナンス要件を固定する**ためにあります。

| テスト | 守っているもの |
|---|---|
| `test_ingest_restores_and_proposes` | 元画像の保全 / 推定が候補・根拠・確度つきで、確定していないこと |
| `test_family_memory_overrides_ai` | 家族の確定が AI の推定より優先され、推定も消えないこと |
| `test_correction_feeds_back_into_next_estimate` | 訂正が後続の推定コンテキストに入ること |
| `test_story_does_not_confirm_relations` | 人物関係を AI が確定しないこと |
| `test_itinerary_times_never_go_backwards` | 休憩を挟んだぶん後続の時刻がずれること |
| `test_audit_records_external_calls_with_policy` | 外部呼び出しが非学習ポリシーつきで記録されること |
| `test_purge_family_removes_photos_and_blobs` | 家族単位の完全削除 |
| `test_share_link_lifecycle` ほか | 共有リンクの期限・失効・横漏れ防止 |
| `test_put_get_query_delete` | Firestore ドライバの読み書き・家族スコープでの絞り込みと一括削除 |
| `test_deceased_photo_waits_for_every_family_member` | 全員の同意が揃うまで動画を生成しないこと |
| `test_one_refusal_blocks_generation` | 一人でも反対したら生成しないこと |
| `test_agent_refuses_to_generate_without_consent` | API を迂回してエージェントを直接叩いても同意ゲートが効くこと |
| `test_generated_clip_is_watermarked_and_moving` | 生成物に透かしが入っていること |
| `test_restore_produces_two_variants` | 修復が2系統でき、どちらを採るかを AI が決めないこと |

これらが落ちる変更は、機能の後退ではなく**設計の前提の後退**です。テストを直す前に、実装を疑ってください。

## ディレクトリ

```
backend/
  app/agents/                ADK のエージェント構成に対応
    orchestrator.py          取り込み→修復→推定→旅程 の進行（自律）
    restore.py               カラー化・退色/折れ修復・ノイズ除去（自律・元画像は常に保全）
    estimate.py              場所/年代を根拠と確度つきで提示（提示まで）
    story.py                 語りの構造化（抽出は自律・確定は家族）
    itinerary.py             現況確認 → 休憩込みの旅程生成（提案まで）
    motion.py                ウゴクアルバム（家族全員の同意が揃うまで生成しない）
    adk.py                   Agent Development Kit へのブリッジ（live 時に LlmAgent 化）
  app/adapters/              gemini / youcam / gmi / ekispert / speech（mock ⇄ live）
  app/infra/                 store.py（Firestore。memory はテスト用）, blobs.py（GCS or ローカル・家族スコープ強制）
  app/api/                   FastAPI ルータ
  tests/                     パイプラインとガバナンスの回帰
frontend/src/pages/          アルバム / 写真 / 巡礼旅 / 共有と記録 / 共有リンクの閲覧
docs/architecture.py         アーキテクチャ図の定義
```

## 変更するときに守ること

この 5 つは設計書の主題そのもので、コードの都合で崩さないでください。

1. **オリジナルは上書きしない** — 修復結果は必ず別キー（`restored/`）に書く
2. **AI は `confirmed` に書かない** — 推定は `estimate`、家族の記憶は `confirmed`。表示は `Photo.resolved_place` を通す
3. **外部 API を叩いたら記録する** — `audit.record_external_call` を通し、非学習ポリシーを証跡に残す
4. **Storage の参照は `make_ref` 経由** — `family/{familyId}/…` 以外は `blobs.py` が弾く
5. **共有は期限つき・失効可能** — 期限なしの公開 URL は作らない
6. **動画生成は同意ゲートの内側** — 故人が写るなら全員の同意が揃うまで生成しない。生成範囲は「その場の自然な動き」に限り、透かしを必ず入れる

### 外部 API を足すとき

`app/adapters/` に mock と live の両方を置き、`get_xxx()` で `*_MODE` を見て切り替えます。
mock は鍵なしでデモが最後まで通る品質にしてください（決定的な出力・それらしい中身）。エージェントからは
ポート（Protocol）越しにしか呼ばず、プロンプトや HTTP の詳細はアダプタの中に閉じ込めます。

### エージェントを足すとき

`agents/base.py` の `Agent` を継承し、`autonomy` を必ず宣言します。

- `autonomous` — 家族の承認なしに進めてよい
- `propose_only` — 提示・提案まで。確定は家族が行う
- `consent_gated` — 家族全員の同意が揃うまで実行しない

`propose_only` のエージェントが確定フィールドに書いていないか、レビューで見てください。

## アーキテクチャ図

[docs/architecture.py](docs/architecture.py)（`diagrams` ライブラリ）で生成します。構成を変えたら図も直します。

```bash
docker compose --profile docs run --rm docs
```

日本語ラベルのため、生成コンテナには graphviz と Noto CJK フォントを入れてあります。

## 主な API

OpenAPI は http://localhost:8080/docs にあります。

| メソッド | パス | 用途 |
|---|---|---|
| POST | `/api/families` | 家族の作成 |
| POST | `/api/families/{id}/members` | 招待（明示招待制） |
| DELETE | `/api/families/{id}` | 削除権の行使 |
| POST | `/api/albums` | アルバム作成 |
| POST | `/api/albums/{id}/photos` | 一括取り込み（修復→推定を自律進行） |
| GET | `/api/jobs/{id}` | 取り込みジョブの進行 |
| POST | `/api/photos/{id}/confirm` | 家族の記憶で確定・訂正 |
| POST | `/api/photos/{id}/reestimate` | 訂正を踏まえた再推定 |
| POST | `/api/photos/{id}/story` | 語り（音声）の記録 |
| POST | `/api/trips` | 旅程の生成 |
| POST | `/api/photos/{id}/variant` | 2系統の修復からどちらを採るか選ぶ |
| POST | `/api/photos/{id}/motion` | ウゴクアルバムの依頼（同意が要るなら待機に入る） |
| POST | `/api/motions/{id}/consent` | 家族ひとりの同意・不同意 |
| GET | `/api/motions/{id}/video` | 生成されたクリップ |
| POST | `/api/share` | 期限つき共有リンクの発行 |
| GET | `/api/shared/{token}` | 共有リンクの閲覧（ログイン不要・読むだけ） |
| POST | `/api/shares/{token}/revoke` | 共有の停止 |
| GET | `/api/families/{id}/audit` | 監査ログ |
| GET | `/api/agents` | エージェント構成と各アダプタのモード |

## モックの中身

`*_MODE=mock` のとき、各アダプタは次のように振る舞います。実 API を入れると同じインターフェースのまま置き換わります。

- **YouCam** — Pillow で ノイズ除去 → 退色補正 → 輝度に応じた着色。カラー化相当の見た目を作る
- **Gemini** — 昭和期の駅・商店街・海岸・神社を題材にした推定フィクスチャ（根拠・確度つき）を、ファイル名から決定的に返す。家族の訂正が入ると該当候補の確度が上がる挙動まで再現する
- **駅すぱあと** — 徒歩→特急→乗換→在来線→徒歩 の区間列を生成（休憩の挿入と体力配慮は本実装側のロジック）
- **Speech-to-Text** — 語りのサンプル書き起こしを返す
- **GMI Cloud** — Pillow で別系統の修復（強めのノイズ除去＋階調伸長／斜めからの再照明）を作り、image-to-video は寄りながら流れる数秒の GIF を生成する。透かしは mock/live どちらでも本実装側で焼き込む

YouCam・駅すぱあと・GMI Cloud の live クライアントは、実キーでの疎通確認がまだです。
鍵を入れる際に公式ドキュメントとエンドポイントを突き合わせてください（コード中にその旨コメントがあります）。

## デプロイ

Cloud Run への手順は [DEPLOY.md](DEPLOY.md) にまとめてあります（CLI・画面操作・GitHub Actions の3通り）。

GitHub Actions の CD（[.github/workflows/deploy.yml](.github/workflows/deploy.yml)）は
**既定で無効**です。リポジトリ変数 `ENABLE_CD` を `true` にするまで、push しても skip されます。
有効にする前に、DEPLOY.md のパターンC を読んで Workload Identity の設定を済ませてください。

デプロイ時にハマりやすいのは次の2点です。

- **CPU 常時割り当てが要る** — 取り込みはレスポンス後にバックグラウンドで走るため、既定の CPU 割り当てだと途中で止まる
- **Apple Silicon から `docker build` するなら `--platform linux/amd64`** — Cloud Build（[cloudbuild.yaml](cloudbuild.yaml)）に投げれば考えなくてよい

## コードのスタイル

- コメントと UI 文言は日本語。コメントは「何をしているか」ではなく「なぜそうしているか」を書く
- 型は付ける（Python は型注釈、フロントは `tsc -b` を通す）
- 既存のファイルの書き方に合わせる。新しい流儀を持ち込む前に、周りのコードを読む
