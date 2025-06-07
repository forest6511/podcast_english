import os
from pathlib import Path
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

class Config:
    # Google Cloud認証
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # プロジェクトルート
    ROOT_DIR = Path(__file__).parent.parent

    # デフォルト設定
    DEFAULT_FPS = 24
    DEFAULT_VIDEO_CODEC = 'libx264'
    DEFAULT_AUDIO_CODEC = 'aac'