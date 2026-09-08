from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

Mode = Literal["mock", "live"]


class Settings(BaseSettings):
    """環境変数だけで mock / live を切り替える。キーが揃うまでは全て mock。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"

    gemini_mode: Mode = "mock"
    youcam_mode: Mode = "mock"
    ekispert_mode: Mode = "mock"
    speech_mode: Mode = "mock"

    # 既定は Firestore（開発はエミュレータ）。memory はテスト用のフォールバック
    db_driver: Literal["firestore", "memory"] = "firestore"
    storage_driver: Literal["local", "gcs"] = "local"

    storage_local_root: str = "/data/storage"
    gcs_bucket: str = ""
    google_cloud_project: str = "omoide-kobo-local"

    gemini_api_key: str = ""
    # 場所・年代推定は画像入力が要るので、マルチモーダル対応の最新 Flash を既定にする
    gemini_model: str = "gemini-3.7-flash"
    youcam_api_key: str = ""
    youcam_secret_key: str = ""
    ekispert_mcp_url: str = ""


    # 設計書 7-1: 学習不使用の技術的担保。live 呼び出し時に必ず監査ログへ記録する。
    no_training_policy: str = "no-training/no-human-review; family-scoped storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
