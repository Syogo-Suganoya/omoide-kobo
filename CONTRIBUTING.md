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

アルバム・写真のメタ情報・旅程・共有リンク・監査ログは、**すべて Firestore** に入ります。
開発ではエミュレータ（`firestore` サービス）、本番では GCP の Firestore を同じコードで使います。
切り替えは `FIRESTORE_EMULATOR_HOST` の有無だけで、アプリ側のコードは変わりません。

写真の実体は Firestore ではなくオブジェクトストレージです（開発はボリューム `omoide-data` の
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
mock 運用では import されないので、開発イメージは軽いままです。

### 依存の追加・更新

直接依存は `requirements.txt`（常に要るもの）と `requirements-live.txt`（実 API 用）に書きます。
**編集したら必ずロックを作り直してください。**

```bash
docker compose run --rm lock
```

`requirements-lock.txt` に全依存が解決済みで並び、イメージはこれを `pip install --no-deps` で入れます。
pip に依存解決をさせないので、live 込みのビルドでも 30 秒ほどで終わります。

ロックを更新せずに `requirements-live.txt` だけ変えると、**変更が反映されないまま**イメージができます。
逆にロックを介さず pip に解かせると、`google-genai` のバージョンを延々と探索して数十分戻ってきません
（これが理由でロック方式にしています）。

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
| `test_ingest_proposes_without_confirming` | 預かった写真をそのまま保管 / 推定が候補・根拠・確度つきで、確定していないこと |
| `test_family_memory_overrides_ai` | 家族の確定が AI の推定より優先され、推定も消えないこと |
| `test_correction_feeds_back_into_next_estimate` | 訂正が後続の推定コンテキストに入ること |
| `test_itinerary_times_never_go_backwards` | 休憩を挟んだぶん後続の時刻がずれること |
| `test_audit_records_external_calls_with_policy` | 外部呼び出しが非学習ポリシーつきで記録されること |
| `test_purge_family_removes_photos_and_blobs` | 家族単位の完全削除 |
| `test_share_link_lifecycle` ほか | 共有リンクの期限・失効・横漏れ防止 |
| `test_course_becomes_sections_in_order` ほか | 駅すぱあとの応答（Point と Line の交互並び）の読み方 |
| `test_put_get_query_delete` | Firestore ドライバの読み書き・家族スコープでの絞り込みと一括削除 |

これらが落ちる変更は、機能の後退ではなく**設計の前提の後退**です。テストを直す前に、実装を疑ってください。

## ディレクトリ

```
backend/
  app/agents/                ADK のエージェント構成に対応
    orchestrator.py          取り込み→推定→旅程 の進行（自律）
    estimate.py              場所/年代を根拠と確度つきで提示（提示まで）
    itinerary.py             現況確認 → 休憩込みの旅程生成（提案まで）
    adk.py                   Agent Development Kit へのブリッジ（live 時に LlmAgent 化）
  app/adapters/              gemini / ekispert（mock ⇄ live）
  app/infra/                 store.py（Firestore。memory はテスト用）, blobs.py（GCS or ローカル・家族スコープ強制）
  app/api/                   FastAPI ルータ
  tests/                     パイプラインとガバナンスの回帰
frontend/src/pages/          はじめに（案内） / わが家 / アルバム / 写真 / 旅 / 共有 / 共有リンクの閲覧
frontend/public/guide/       案内ページ「使い方」のスクリーンショット
docs/architecture.py         アーキテクチャ図の定義
```

### 画面の考え方

`/home`（わが家）が作業の起点。`components/todo.tsx` の `buildTodos` が家族のいまの状態から
「次にやること」を組み立て、上から片づければ写真投入から旅程・共有まで進むようにしてある。
写真ページの `components/nowbar.tsx` も同じ役割で、その1枚について次の一手だけを出す。

**入口で入力を求めない。** 家族名は「わたしの家族」で自動作成し、`/home` の見出しから
`PATCH /api/families/{id}` で変えられるようにしてある（初回に名前を考えさせない）。
アルバムの1冊目も同時に作り、写真を入れる画面へ直行する。

**メニューは動詞で並べる。** `components/nav.tsx`。画面名（わが家・旅・共有）ではなく
「押すと何ができるか」を出す。狭い画面では CSS で下端の固定バーに回すので、DOM は1つだけにしておく。
メニューの呼び名は、その画面の見出しと案内ページの文言に揃える（同じ場所を別の名前で呼ばない）。

**家族が確定する欄に、AI の値を初期値として入れない。** 場所も年代も、候補は
プレースホルダ（`例: ◯◯`）と「「◯◯」を入れる」ボタンで示し、押してもらう。
初期値に入れると、触っていない欄がそのまま「家族が確定した記憶」として保存される（設計書 7-2）。

**まだ確かめていない名前は、確定した名前と同じ顔で出さない。** 一覧のキャプションなどで
AI の候補を出すときは `PlaceLabel` を使い、「「◯◯」かも＋候補」の形にする。

**メニューは、深い画面でも現在地を示す。** `/albums` `/photos` は「写真を調べる」の配下として
`nav.tsx` の `owns` に並べてある。画面を足したら、どのタブの配下かをここに書く。

**押した結果は必ず画面で言う。** 成否が環境に左右される操作（クリップボードへのコピーなど）は、
成功したときだけ「できました」と言い、駄目なときは代わりの手（URL を選んで写す）をその場に出す。
成功を決め打ちで書かない。

**押せないボタンは、押せない理由を隣に書く。** 旅程・共有リンク・招待・場所の確定・削除は、
条件を満たすまで `disabled` にしたうえで「◯◯すると押せます」を並べて出す。
選ばせる UI（旅の写真選び）は、色の変化だけに頼らず「選ぶ／✓n番目」の札を出す。

**画面の文言は、いまの中身に合わせて変える。** 例：アルバムの説明は 0枚・推定中・確認待ち・全確定で
別の文を出す（画面に無い札を探させない）。写真ページの「家族にたずねる」は、
`<details>` の開閉を進み具合に連動させ、いまやることが一番大きく見えるようにする。

**エージェント名・接続モード・監査ログは画面に出さない。** ユーザーが知る必要のない実装の都合なので、
`GET /api/agents` と `GET /api/families/{id}/audit` は残しつつ、画面からは呼ばない。
監査ログの記録自体は設計書 7 章の要件なので、バックエンドでは従来どおり残し続けること。

### 使い方のスクリーンショット

案内ページの「使い方」は、`frontend/public/guide/` の画像をスライドで見せます。
**手で撮らず、[docs/shots.js](docs/shots.js) に撮らせます。**

```bash
GEMINI_MODE=mock EKISPERT_MODE=mock docker compose --profile shots up --build shots
```

利用者と同じ順に画面を操作して6枚撮るので、画面を変えたら流し直すだけで追随します。

| ファイル | 撮る画面 |
|---|---|
| `01-family.png` | 「写真を調べる」の入口（写真を入れる） |
| `02-upload.png` | 写真を入れる枠 |
| `03-progress.png` | 取り込みの進行 |
| `04-confirm.png` | AI の推定と家族の確定フォーム |
| `05-trip.png` | 旅程 |
| `06-share.png` | 共有リンク |

撮る前に**家族を全部消します**（1枚目が「家族がまだ無い人の入口」のため）。
開発のエミュレータはメモリ上なので消えて困るものは入っていませんが、
本物の Firestore を指した状態では流さないでください。

`GEMINI_MODE=mock` を付けるのは、鍵や live 依存の有無に左右されず、毎回同じ推定結果で撮れるからです。
付け忘れて live のまま流すと、推定が通らない理由を添えて途中で止まります。

**案内ページ側の窓（`.guide .shot .win`）は 16:10 に固定**で、画面を送っても伸び縮みしません。
横は必ず全部見え、入りきらない縦は下が切れます（`object-fit: cover` にすると左右が切れて、
写真ページの左の列が消えてしまうので使いません）。

撮る側は高さを決め打ちせず、「どの見出しからどの要素まで」で指定します（`frame()` の `from` / `to`）。
`from` に置いた見出しが窓の頭に来るので、下が切れても大事なところは残ります。

説明文とファイル名の対応は [LandingPage.tsx](frontend/src/pages/LandingPage.tsx) の `STEPS` にあります。
**手順を足し引きしたら、`STEPS` と `shots.js` の両方を直してください。**

## 変更するときに守ること

この 5 つは設計書の主題そのもので、コードの都合で崩さないでください。

1. **預かった写真に手を加えない** — 加工した画像で元を置き換えない。保存は `original/` のみ
2. **AI は `confirmed` に書かない** — 推定は `estimate`、家族の記憶は `confirmed`。表示は `Photo.resolved_place` を通す
3. **外部 API を叩いたら記録する** — `audit.record_external_call` を通し、非学習ポリシーを証跡に残す
4. **Storage の参照は `make_ref` 経由** — `family/{familyId}/…` 以外は `blobs.py` が弾く
5. **共有は期限つき・失効可能** — 期限なしの公開 URL は作らない

### 外部 API を足すとき

`app/adapters/` に mock と live の両方を置き、`get_xxx()` で `*_MODE` を見て切り替えます。
mock は鍵なしでデモが最後まで通る品質にしてください（決定的な出力・それらしい中身）。エージェントからは
ポート（Protocol）越しにしか呼ばず、プロンプトや HTTP の詳細はアダプタの中に閉じ込めます。

### エージェントを足すとき

`agents/base.py` の `Agent` を継承し、`autonomy` を必ず宣言します。

- `autonomous` — 家族の承認なしに進めてよい
- `propose_only` — 提示・提案まで。確定は家族が行う

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
| PATCH | `/api/families/{id}` | 家族の名前を変える |
| POST | `/api/families/{id}/members` | 招待（明示招待制） |
| DELETE | `/api/families/{id}` | 削除権の行使 |
| POST | `/api/albums` | アルバム作成 |
| POST | `/api/albums/{id}/photos` | 一括取り込み（場所・年代の推定を自律進行） |
| GET | `/api/families/{id}/photos` | 家族の写真をまとめて取得（「いまやること」の集計用） |
| GET | `/api/jobs/{id}` | 取り込みジョブの進行 |
| POST | `/api/photos/{id}/confirm` | 家族の記憶で確定・訂正 |
| POST | `/api/photos/{id}/reestimate` | 訂正を踏まえた再推定 |
| POST | `/api/trips` | 旅程の生成 |
| POST | `/api/share` | 期限つき共有リンクの発行 |
| GET | `/api/shared/{token}` | 共有リンクの閲覧（ログイン不要・読むだけ） |
| POST | `/api/shares/{token}/revoke` | 共有の停止 |
| GET | `/api/families/{id}/audit` | 監査ログ |
| GET | `/api/agents` | エージェント構成と各アダプタのモード |

## モックの中身

`*_MODE=mock` のとき、各アダプタは次のように振る舞います。実 API を入れると同じインターフェースのまま置き換わります。

- **Gemini** — 昭和期の駅・商店街・海岸・神社を題材にした推定フィクスチャ（根拠・確度つき）を、ファイル名から決定的に返す。家族の訂正が入ると該当候補の確度が上がる挙動まで再現する
- **駅すぱあと** — 徒歩→特急→乗換→在来線→徒歩 の区間列を生成（休憩の挿入と体力配慮は本実装側のロジック）

## 駅すぱあと API MCP サーバー

`EKISPERT_MODE=live` のとき、[公式の MCP サーバー](https://github.com/ValLaboratory/ekispert-api-mcp-server-docs)
（`https://api-mcp.ekispert.jp/mcp`）へ Streamable HTTP で繋ぎます。素の JSON-RPC POST では通らないので、
`initialize` → `notifications/initialized` → `tools/call` の順に投げ、応答は SSE でも JSON でも読めるようにしてあります。

- 経路探索のツール名は `ekispert_api_search_routes`（中身は `/search/course/extreme`）
- 出発・経由・目的地は **コロン区切りの `viaList` 1本**（駅名・駅コード・住所・座標のいずれも可）
- アクセスキーは `ekispert-api-access-key` ヘッダ。`EKISPERT_API_KEY` に入れる

疎通確認は、アプリを立ち上げずにこれだけで試せます。

```bash
docker compose run --rm api python -m scripts.check_ekispert 東京 京都
```

握手とツール一覧までは鍵なしで確認済みです（サーバー v0.3.0・ツール6種）。
**経路探索そのものは実キーでの確認がまだ**なので、鍵を入れた人は上のコマンドを一度通してください。

> [!CAUTION]
> ダイヤ探索（`departure` / `arrival` / `lastTrain` / `firstTrain`）と `time` パラメータは、
> **2026年後半以降は専用アクセスキーが必要になる予定**と公式に告知されています（発行手続きは準備中）。
> 旅程は出発時刻を指定して組むのでこの制限に当たります。塞がれた場合は `searchType` を既定の
> `plain`（平均待ち時間探索）に落とし、`time` を送らない形に切り替えてください。

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
