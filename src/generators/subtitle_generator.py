from pathlib import Path
from typing import List, Tuple
from pydub import AudioSegment
import math

from ..models.series import Episode, Settings
from ..utils.path_manager import PathManager

class SubtitleGenerator:
    def __init__(self, settings: Settings, path_manager: PathManager):
        self.settings = settings
        self.pm = path_manager

    def generate_subtitles(self, episode: Episode, audio_path: Path) -> Path:
        """字幕ファイル（SRT）を生成"""
        print(f"Generating subtitles for episode {episode.id}")

        # 各音声ファイルの長さを取得して、正確なタイミングを計算
        timings = self._calculate_accurate_timings(episode)

        # SRTファイルを生成
        output_path = self.pm.get_subtitle_path(episode.id)
        self._write_srt(timings, output_path)

        print(f"Subtitles saved to: {output_path}")
        return output_path

    def _calculate_accurate_timings(self, episode: Episode) -> List[Tuple[float, float, str]]:
        """各音声ファイルの実際の長さから正確なタイミングを計算"""
        timings = []
        current_time = 0.0

        for idx, conv in enumerate(episode.conversations):
            # 個別の音声ファイルパスを取得
            audio_file = self.pm.get_audio_path(episode.id, conv.speaker, idx)

            if audio_file.exists():
                # 音声ファイルの実際の長さを取得
                audio = AudioSegment.from_mp3(str(audio_file))
                duration = len(audio) / 1000.0  # ミリ秒から秒へ
            else:
                # ファイルがない場合は推定値を使用
                words = len(conv.text.split())
                duration = words / 2.5  # 1分あたり150語

            # 開始時間と終了時間
            start_time = current_time
            end_time = current_time + duration

            timings.append((start_time, end_time, conv.text))

            # 次の会話までの間隔を追加
            current_time = end_time + self.settings.pause_between_lines

        return timings

    def _write_srt(self, timings: List[Tuple[float, float, str]], output_path: Path):
        """SRTファイルを書き込み"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for idx, (start, end, text) in enumerate(timings, 1):
                # SRT形式で時間をフォーマット
                start_str = self._format_time(start)
                end_str = self._format_time(end)

                f.write(f"{idx}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{text}\n")
                f.write("\n")

    def _format_time(self, seconds: float) -> str:
        """秒をSRT時間形式に変換 (00:00:00,000)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"