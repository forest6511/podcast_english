from pathlib import Path
import shutil
from typing import Optional

class PathManager:
    def __init__(self, series_id: str):
        self.series_id = series_id
        self.root = Path(__file__).parent.parent.parent

        # 入力パス
        self.data_dir = self.root / "data" / "series" / series_id
        self.series_json = self.data_dir / "series.json"

        # 出力パス
        self.output_dir = self.root / "output" / "series" / series_id
        self.audio_dir = self.output_dir / "audio"
        self.subtitles_dir = self.output_dir / "subtitles"
        self.video_dir = self.output_dir / "video"

        # アセットパス
        self.assets_dir = self.root / "assets"
        self.backgrounds_dir = self.assets_dir / "backgrounds"

    def clean_output(self):
        """出力ディレクトリをクリーンアップ"""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

        # ディレクトリを再作成
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.subtitles_dir.mkdir(parents=True, exist_ok=True)
        self.video_dir.mkdir(parents=True, exist_ok=True)

    def get_episode_audio_dir(self, episode_id: str) -> Path:
        """エピソードの音声ディレクトリ"""
        path = self.audio_dir / f"ep{episode_id}"
        path.mkdir(exist_ok=True)
        return path

    def get_audio_path(self, episode_id: str, speaker: str, line_num: int) -> Path:
        """個別音声ファイルのパス"""
        audio_dir = self.get_episode_audio_dir(episode_id)
        return audio_dir / f"{speaker}_{line_num:03d}.mp3"

    def get_combined_audio_path(self, episode_id: str) -> Path:
        """結合音声ファイルのパス"""
        audio_dir = self.get_episode_audio_dir(episode_id)
        return audio_dir / "combined.mp3"

    def get_subtitle_path(self, episode_id: str) -> Path:
        """字幕ファイルのパス"""
        return self.subtitles_dir / f"ep{episode_id}.srt"

    def get_video_path(self, episode_id: str, episode_title: str) -> Path:
        """動画ファイルのパス"""
        safe_title = episode_title.lower().replace(" ", "_")
        return self.video_dir / f"ep{episode_id}_{safe_title}.mp4"

    def get_background_path(self, filename: Optional[str] = None) -> Path:
        """背景画像のパス"""
        if filename:
            return self.backgrounds_dir / filename
        return self.backgrounds_dir / "podcast_bg.jpg"