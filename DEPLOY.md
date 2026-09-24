# デプロイ手順

オモイデ工房を Google Cloud（Cloud Run）に載せる手順です。**CLI** と **画面操作** の2通りを載せます。
どちらでも結果は同じなので、やりやすい方を選んでください。
main への push で自動デプロイする **GitHub Actions（CD）** も用意してあります（[パターンC](#パターンc-github-actionscd)。既定は無効）。

[Dockerfile.deploy](Dockerfile.deploy) が PWA をビルドして API と同居させた 1 コンテナを作るので、
デプロイするサービスは 1 つだけです（`/` が画面、`/api` が API）。

## 作るもの

| リソース | 用途 |
|---|---|
| Cloud Run サービス | アプリ本体（api + PWA） |
| Artifact Registry | コンテナイメージの置き場 |
| Cloud Storage バケット | 写真（家族限定・公開しない） |
| Firestore | アルバム・写真のメタ情報・物語・旅程・共有リンク・監査ログ |
| Secret Manager | Gemini / 駅すぱあと のキー |
| サービスアカウント | Cloud Run が上記にアクセスするための身元 |

以下の値で書いてあります。プロジェクトを別名で作った場合は読み替えてください。

```
プロジェクトID : omoide-kobo
リージョン     : asia-northeast1
サービス名     : omoide-kobo
バケット名     : omoide-kobo-family
リポジトリ名   : omoide
```

バケット名だけは **Google Cloud 全体で一意**である必要があります。`omoide-kobo-family` が
すでに使われていたら、`omoide-kobo-family-2026` のように後ろを足してください。

## 先に決めること

### 鍵を入れるか、モックのまま出すか

**鍵なしでも動きます。** 発表用にとりあえず URL が欲しいだけなら、外部 API は `mock` のままで構いません。

一方、**保存先は必ず Firestore と Cloud Storage を繋いでください**。Cloud Run のインスタンスは使い捨てなので、
`DB_DRIVER=memory` / `STORAGE_DRIVER=local` のままだとスケールや再起動でデータが消えます
（`memory` はテスト用のフォールバックで、運用に使うものではありません）。

| 目的 | 設定 |
|---|---|
| デモ（鍵なし） | 全て `mock` / `DB_DRIVER=firestore` / `STORAGE_DRIVER=gcs` |
| 本番相当 | 各 `*_MODE=live` + キー / `firestore` / `gcs` |

### CPU の割り当て

取り込み（場所・年代の推定）は**レスポンスを返した後にバックグラウンドで走ります**。
Cloud Run の既定はリクエスト処理中しか CPU が回らないため、**CPU を常時割り当て**にしてください。
これをしないと、アップロードは成功するのにパイプラインが途中で止まります。

- CLI: `--no-cpu-throttling`
- 画面: 「CPU の割り当て」で **「CPU を常に割り当てる」**

---

# パターンA: CLI

## 1. 準備

```bash
export PROJECT=omoide-kobo
export REGION=asia-northeast1
export SERVICE=omoide-kobo
export BUCKET=$PROJECT-family
export REPO=omoide-kobo

gcloud config set project "$PROJECT"

# ターミナルを開き直すと消えます。以降の手順で空になっていないか、都度この確認を
echo "PROJECT=[$PROJECT] REGION=[$REGION] SERVICE=[$SERVICE] BUCKET=[$BUCKET] REPO=[$REPO]"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

## 2. 置き場を作る

```bash
# イメージの置き場
gcloud artifacts repositories create $REPO \
  --repository-format=docker --location=$REGION

# 写真のバケット（公開アクセスは付けない）
gcloud storage buckets create gs://$BUCKET \
  --location=$REGION --uniform-bucket-level-access

# Firestore（ネイティブモード。プロジェクトに1つ。アプリのデータはすべてここに入る）
gcloud firestore databases create --location=$REGION
```

## 3. キーを Secret Manager に入れる（live にするときだけ）

```bash
printf '%s' 'YOUR_GEMINI_KEY' | gcloud secrets create gemini-key --data-file=-
printf '%s' 'YOUR_EKISPERT_KEY' | gcloud secrets create ekispert-key --data-file=-
```

キーをシェル履歴に残したくなければ `--data-file=path/to/key.txt` を使ってください。

## 4. サービスアカウントと権限

```bash
export SA=omoide-kobo-run@$PROJECT.iam.gserviceaccount.com

gcloud iam service-accounts create omoide-kobo-run \
  --display-name="オモイデ工房 Cloud Run"

# Firestore への読み書き
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/datastore.user"

# バケットへの読み書き（プロジェクト全体ではなくバケット単位に絞る）
gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"

# シークレットの読み取り（live のときだけ）
gcloud secrets add-iam-policy-binding gemini-key \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding ekispert-key \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
```

## 5. ビルドして上げる

**Apple Silicon の Mac から `docker build` する場合は `--platform linux/amd64` が必須です。**
これを忘れると、デプロイは通るのに起動時に exec format error で落ちます。

```bash
# zsh では $SERVICE:latest の ":l" が小文字化の修飾子として食われるため、波括弧が必須
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:latest"
echo "$IMAGE"   # asia-northeast1-docker.pkg.dev/omoide-kobo/omoide/omoide-kobo:latest

gcloud auth configure-docker "${REGION}-docker.pkg.dev"
docker build --platform linux/amd64 -f Dockerfile.deploy -t "$IMAGE" .
docker push "$IMAGE"
```

Cloud Build に投げれば、手元のアーキテクチャを気にせず済みます（こちらが楽です）。
[cloudbuild.yaml](cloudbuild.yaml) が `Dockerfile.deploy` を使ってビルドし、そのまま Artifact Registry に上げます。

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE=$IMAGE
```

## 6. デプロイ

```bash
gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --service-account $SA \
  --allow-unauthenticated \
  --no-cpu-throttling \
  --memory 1Gi \
  --timeout 600 \
  --set-env-vars "DB_DRIVER=firestore,STORAGE_DRIVER=gcs,GCS_BUCKET=$BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT,GEMINI_MODE=live,EKISPERT_MODE=live" \
  --set-secrets "GEMINI_API_KEY=gemini-key:latest,EKISPERT_API_KEY=ekispert-key:latest"
```

実 API に切り替えるときは、`*_MODE` を `live` にしてシークレットを渡します。

```bash
gcloud run services update $SERVICE --region $REGION \
  --set-env-vars "GEMINI_MODE=live,EKISPERT_MODE=live,GEMINI_MODEL=gemini-3.7-flash" \
  --set-secrets "GEMINI_API_KEY=gemini-key:latest,EKISPERT_API_KEY=ekispert-key:latest"
```

`--allow-unauthenticated` を付けるのは、**共有リンクを受け取った家族がログインなしで開ける**ようにするためです。
身内だけで試すなら外して構いません（その場合は共有リンクも開けなくなります）。

## 7. 動いているか確かめる

```bash
URL=$(gcloud run services describe $SERVICE --region $REGION --format='value(status.url)')

curl -s $URL/api/healthz                # {"status":"ok",...}
curl -s $URL/api/agents | head -c 400   # 各アダプタが mock か live か
open $URL                               # 画面
```

---

# パターンB: 画面操作（Google Cloud コンソール）

コンソールの文言は変わることがあります。ボタン名が違ったら、同じ意味の項目を探してください。

## 1. プロジェクトと API

1. https://console.cloud.google.com を開き、上部でプロジェクトを選ぶ（なければ「新しいプロジェクト」）
2. 課金が有効になっていることを確認（「お支払い」）
3. 検索窓で「API とサービス」→「API とサービスの有効化」を開き、次を有効にする
   - Cloud Run Admin API
   - Artifact Registry API
   - Cloud Firestore API
   - Cloud Storage API
   - Secret Manager API
   - Cloud Build API

## 2. Artifact Registry（イメージの置き場）

1. 検索窓で「Artifact Registry」→「リポジトリを作成」
2. 名前 `omoide-kobo` / 形式 **Docker** / ロケーションタイプ **リージョン** / `asia-northeast1`
3. 「作成」

## 3. Cloud Storage（写真の置き場）

1. 検索窓で「Cloud Storage」→「バケットを作成」
2. 名前 `omoide-kobo-family`（世界で一意。取られていたら末尾を足す）
3. ロケーション **リージョン** / `asia-northeast1`
4. アクセス制御は **均一**
5. **「このバケットに対する公開アクセスを禁止する」にチェックを入れたまま**作成する

## 4. Firestore

1. 検索窓で「Firestore」→「データベースを作成」
2. **ネイティブモード**を選ぶ
3. ロケーション `asia-northeast1` →「データベースを作成」

## 5. Secret Manager（live にするときだけ）

1. 検索窓で「Secret Manager」→「シークレットを作成」
2. 名前 `gemini-key`、値に API キーを貼り「シークレットを作成」
3. 同じ手順で、使うぶんだけ作る

   | 名前 | 貼る値 |
   |---|---|
   | `ekispert-key` | 駅すぱあと API のアクセスキー |

## 6. サービスアカウント

1. 「IAM と管理」→「サービス アカウント」→「サービス アカウントを作成」
2. 名前 `omoide-kobo-run` →「作成して続行」
3. ロールに **Cloud Datastore ユーザー** を追加 →「完了」
4. Cloud Storage → 作ったバケット →「権限」タブ →「アクセスを許可」
   - プリンシパル: `omoide-kobo-run@omoide-kobo.iam.gserviceaccount.com`
   - ロール: **Storage オブジェクト管理者**
5. live にするなら、Secret Manager の各シークレット →「権限」→ 同じプリンシパルに
   **Secret Manager のシークレット アクセサー** を付与

## 7. イメージを上げる

イメージのビルドだけは手元（またはクラウドシェル）で行います。画面右上の **「Cloud Shell をアクティブにする」**
（`>_` アイコン）を押すと、ブラウザ内のターミナルが開きます。ここで実行すればアーキテクチャの問題も起きません。

```bash
git clone https://github.com/Syogo-Suganoya/omoide-kobo.git && cd omoide-kobo

gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_IMAGE=asia-northeast1-docker.pkg.dev/omoide-kobo/omoide/omoide-kobo:latest
```

数分で終わります。完了すると Artifact Registry の `omoide` リポジトリにイメージが並びます。

## 8. Cloud Run にデプロイ

1. 検索窓で「Cloud Run」→「コンテナをデプロイ」→「サービス」
2. **コンテナ イメージの URL**：「選択」を押し、Artifact Registry から上げたイメージを選ぶ
3. **サービス名** `omoide-kobo`、**リージョン** `asia-northeast1`
4. **認証**：「未認証の呼び出しを許可」を選ぶ（共有リンクを家族が開けるようにするため）
5. 「コンテナ、ボリューム、ネットワーキング、セキュリティ」を開く
   - **コンテナ**タブ
     - メモリ **1 GiB**
     - リクエストのタイムアウト **600** 秒
     - **CPU の割り当て**：**「CPU を常に割り当てる」**（バックグラウンド処理が止まらないように）
   - **変数とシークレット**タブ
     - 「変数を追加」で次を入れる

       | 名前 | 値 |
       |---|---|
       | `DB_DRIVER` | `firestore` |
       | `STORAGE_DRIVER` | `gcs` |
       | `GCS_BUCKET` | `omoide-kobo-family` |
       | `GOOGLE_CLOUD_PROJECT` | `omoide-kobo` |
       | `GEMINI_MODE` | `mock`（実 API を使うなら `live`） |
       | `EKISPERT_MODE` | `mock` |

     - live にする場合は「シークレットの参照」から下記を**環境変数として公開**で追加（バージョンは `latest`）

       | シークレット | 環境変数の名前 |
       |---|---|
       | `gemini-key` | `GEMINI_API_KEY` |
       | `ekispert-key` | `EKISPERT_API_KEY` |
   - **セキュリティ**タブ
     - **サービス アカウント** に `omoide-kobo-run@…` を選ぶ
6. 「作成」を押す。1〜2分で URL が表示されます

## 9. 動いているか確かめる

1. 表示された URL を開く（画面が出る）
2. URL の末尾に `/api/healthz` を付けて開くと `{"status":"ok",...}` が返る
3. `/api/agents` で各アダプタが `mock` か `live` か確認できる
4. うまく動かないときは Cloud Run のサービス →「ログ」タブを見る

---

# パターンC: GitHub Actions（CD）

[.github/workflows/deploy.yml](.github/workflows/deploy.yml) が、テスト → イメージビルド → Cloud Run へのリリース →
起動確認 まで通します。**いまは無効**で、push しても何も起きません（ジョブが skip されます）。

初回だけは CLI か画面操作でリソースを作っておく必要があります（Artifact Registry・バケット・Firestore・
サービスアカウント）。CD が作るのはイメージとリビジョンだけです。

## 1. GitHub から鍵なしで入れるようにする

サービスアカウントの JSON 鍵をリポジトリに置く方式は避け、Workload Identity 連携（鍵ファイル不要）を使います。

```bash
export PROJECT=omoide-kobo
export REPO_SLUG=Syogo-Suganoya/omoide-kobo
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')

gcloud services enable iamcredentials.googleapis.com

gcloud iam workload-identity-pools create github --location=global \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --location=global --workload-identity-pool=github \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$REPO_SLUG'"
```

`--attribute-condition` が要点です。**このリポジトリからの実行だけ**を受け入れます。これを省くと、
他人のリポジトリからでもトークンを交換できてしまいます。

デプロイを実行するサービスアカウントを作り、GitHub からの成りすましを許可します。

```bash
export DEPLOYER=omoide-kobo-deployer@$PROJECT.iam.gserviceaccount.com

gcloud iam service-accounts create omoide-kobo-deployer --display-name="GitHub Actions デプロイ用"

for role in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.writer roles/storage.admin; do
  gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$DEPLOYER" --role="$role"
done

# デプロイ用SAが、実行用SA（omoide-kobo-run）としてサービスを動かせるようにする
gcloud iam service-accounts add-iam-policy-binding omoide-kobo-run@$PROJECT.iam.gserviceaccount.com \
  --member="serviceAccount:$DEPLOYER" --role="roles/iam.serviceAccountUser"

# ビルドを実行するSA（既定は Compute Engine のもの）としても振る舞えるようにする。
# これが無いと gcloud builds submit が PERMISSION_DENIED「caller does not have permission
# to act as service account」で落ちる（Cloud Run への権限とは別物）
gcloud iam service-accounts add-iam-policy-binding \
  $PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --member="serviceAccount:$DEPLOYER" --role="roles/iam.serviceAccountUser"

# GitHub の当該リポジトリからだけ、このSAを使えるようにする
gcloud iam service-accounts add-iam-policy-binding $DEPLOYER \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$REPO_SLUG"

echo "WIF_PROVIDER=projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github"
```

## 2. GitHub 側に値を入れる

リポジトリの **Settings → Secrets and variables → Actions → Variables** に、次を **Variables**（Secrets ではない）として登録します。
いずれも秘密ではありません。秘密は Secret Manager 側にあり、Cloud Run が直接読みます。

| 変数 | 値 |
|---|---|
| `WIF_PROVIDER` | 上のコマンドが出力した `projects/…/providers/github` |
| `DEPLOY_SERVICE_ACCOUNT` | `omoide-kobo-deployer@omoide-kobo.iam.gserviceaccount.com` |
| `RUNTIME_SERVICE_ACCOUNT` | `omoide-kobo-run@omoide-kobo.iam.gserviceaccount.com` |
| `GCS_BUCKET` | `omoide-kobo-family` |
| `GEMINI_MODE` ほか | 省略可（未設定なら `mock`）。実 API を使うなら `live` |

### gh コマンドで入れる

画面を開かずに済ませるならこちら。`gh auth login` 済みで、リポジトリの中で実行してください。

```bash
gh variable set WIF_PROVIDER --body "projects/114688237019/locations/global/workloadIdentityPools/github/providers/github"
gh variable set DEPLOY_SERVICE_ACCOUNT --body "omoide-kobo-deployer@omoide-kobo.iam.gserviceaccount.com"
gh variable set RUNTIME_SERVICE_ACCOUNT --body "omoide-kobo-run@omoide-kobo.iam.gserviceaccount.com"
gh variable set GCS_BUCKET --body "omoide-kobo-family"
```

実 API を使うなら、使うものだけ `live` にします（未設定なら `mock`）。

```bash
gh variable set GEMINI_MODE --body "live"
gh variable set EKISPERT_MODE --body "live"
```

入った値の確認と、消すとき。

```bash
gh variable list
gh variable delete GEMINI_MODE
```

**`gh secret` ではなく `gh variable` です。** ここに入れるのは秘密ではありません
（鍵は Secret Manager にあり、Cloud Run が直接読みます）。`gh secret` に入れるとログでマスクされ、
デプロイが失敗したときに値の取り違えを目視で追えなくなります。

## 3. CD を有効にする

**変数 `ENABLE_CD` を `true` にした時点で、main への push が本番へ出ます。** それまでは無効です。

| やりたいこと | 操作 | gh |
|---|---|---|
| 自動デプロイを有効にする | Variables に `ENABLE_CD` = `true` を追加 | `gh variable set ENABLE_CD --body "true"` |
| 一時的に止める | `ENABLE_CD` を `false` にする（削除でも可） | `gh variable set ENABLE_CD --body "false"` |
| 有効にせず1回だけ流す | Actions タブ →「Cloud Run へデプロイ」→ Run workflow → **confirm にチェック** | `gh workflow run deploy.yml -f confirm=true` |

`backend/` `frontend/` `Dockerfile.deploy` `cloudbuild.yaml` のいずれかが変わった push でだけ走ります。
ドキュメントだけの変更では動きません。

### いま何が出ているかを GitHub で見る

デプロイのジョブは `production` という **Environment** に紐づけてあります。
初回のデプロイで GitHub 側に自動で作られるので、事前の準備は要りません。

- リポジトリのトップ右側の **Environments**、または **Settings → Environments** に履歴が並びます
- 現在の URL は、デプロイのたびに `gcloud run services describe` で取った実際の値が入ります
  （ワークフローに URL を書き写していないので、サービスを作り直しても食い違いません）

承認を挟みたくなったら、**Settings → Environments → production → Required reviewers** を付けます。
ワークフローは変えずに、デプロイの手前で止まるようになります。

## 4. 失敗したときは

- **テストで止まった** — 本番には出ていません。ローカルで `docker compose run --rm api pytest` を通してから push
- **リリース後の起動確認で落ちた** — 新しいリビジョンは配信されているので、[元に戻す](#元に戻す)でひとつ前へ戻す
- **認証で落ちた** — `WIF_PROVIDER` と `DEPLOY_SERVICE_ACCOUNT` の綴り、`--attribute-condition` のリポジトリ名を確認
- **ビルドで `PERMISSION_DENIED: caller does not have permission to act as service account`** —
  デプロイ用SAに、ビルド実行SAへの `roles/iam.serviceAccountUser` が無い。エラーに出た数字は
  サービスアカウントの `uniqueId` なので、次で実体を突き止めてから付与する

  ```bash
  BUILD_SA=$(gcloud iam service-accounts list --project $PROJECT \
    --filter="uniqueId=<エラーに出た数字>" --format='value(email)')
  echo "$BUILD_SA"

  gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA" \
    --member="serviceAccount:$DEPLOYER" --role="roles/iam.serviceAccountUser"
  ```

- **ビルド実行SA自身の権限が足りない** — 続けて `artifactregistry.writer` と `logging.logWriter` が要る
  （`cloudbuild.yaml` は `CLOUD_LOGGING_ONLY` なので、ログ書き込み権限が無いとビルドが開始できない）

  ```bash
  for role in roles/artifactregistry.writer roles/logging.logWriter; do
    gcloud projects add-iam-policy-binding $PROJECT \
      --member="serviceAccount:$BUILD_SA" --role="$role"
  done
  ```

---

# デプロイした後

## 更新する

イメージを作り直して、同じサービスにデプロイし直すだけです。

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions=_IMAGE=$IMAGE
gcloud run deploy $SERVICE --image $IMAGE --region $REGION
```

画面の場合は、サービスを開いて「新しいリビジョンの編集とデプロイ」です。

## 元に戻す

Cloud Run はリビジョンを残しているので、前の状態にすぐ戻せます。

```bash
gcloud run services update-traffic $SERVICE --region $REGION --to-revisions=<前のリビジョン名>=100
```

画面では「リビジョン」タブ →「トラフィックを管理」。

## 片付ける

放置してもほぼ無料ですが（Cloud Run は 0 インスタンスまで縮む）、消すなら次の通りです。

```bash
gcloud run services delete $SERVICE --region $REGION
gcloud storage rm -r gs://$BUCKET
gcloud artifacts repositories delete $REPO --location=$REGION
```

Firestore のデータは、アプリの「共有と記録」から家族単位で完全削除できます。

## 気をつけること

- **バケットは公開しない。** 写真は必ず API 経由で出します。バケットに `allUsers` を付けないでください
- **共有リンクは期限つき。** サービスを未認証で公開しても、写真が見えるのは有効なトークンを持つ人だけです
- **キーは環境変数に直書きしない。** Secret Manager 経由にしてください（Cloud Run の設定画面にも平文で残りません）
- **リージョンは揃える。** Cloud Run・バケット・Firestore・Artifact Registry を同じリージョンにすると速く、安くなります

Sources:
- [Deploy container images to Cloud Run services](https://docs.cloud.google.com/run/docs/deploying)
- [Configure secrets for services | Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
- [Deploying to Cloud Run | Artifact Registry](https://docs.cloud.google.com/artifact-registry/docs/integrate-cloud-run)
