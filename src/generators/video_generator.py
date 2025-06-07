from pathlib import Path
from moviepy import VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip, ColorClip, TextClip
import numpy as np
from typing import Union, List, Tuple
from PIL import Image, ImageDraw
import io

from ..models.series import Episode, Settings
from ..utils.path_manager import PathManager

class VideoGenerator:
    def __init__(self, settings: Settings, path_manager: PathManager):
        self.settings = settings
        self.pm = path_manager

    def generate_video(self, episode: Episode, audio_path: Path, subtitle_path: Path) -> Path:
        """動画を生成"""
        print(f"Generating video for episode {episode.id}: {episode.title}")

        # 音声を読み込み
        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration

        # 背景画像を読み込み
        background_path = self.pm.get_background_path()
        background = ImageClip(str(background_path), duration=duration)

        # 背景を1920x1080にリサイズ
        background = background.resized((1920, 1080))

        # 音声波形を作成
        waveform = self._create_simple_waveform(duration)

        # ベースビデオを合成（静的な字幕背景は含めない）
        base_video = CompositeVideoClip([
            background,
            waveform
        ])

        # 字幕と動的背景を追加
        video_with_subtitles = self._add_subtitles_with_dynamic_bg(base_video, subtitle_path)

        # 音声を設定
        final_video = video_with_subtitles.with_audio(audio_clip)

        # 動画を保存
        output_path = self.pm.get_video_path(episode.id, episode.title)
        final_video.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264',
            audio_codec='aac',
            threads=4
        )

        # クリーンアップ
        audio_clip.close()
        final_video.close()

        print(f"Video saved to: {output_path}")
        return output_path

    def _format_subtitle_text(self, text: str, max_chars_per_line: int = 35) -> str:
        """長いテキストを適切に改行（最大3行）"""
        words = text.split()

        # 短いテキストはそのまま返す
        if len(text) <= max_chars_per_line:
            return text

        # 長いテキストを行に分割
        lines = []
        current_line = []
        current_length = 0

        for word in words:
            # 単語を追加した場合の長さを計算
            word_length = len(word)
            if current_length == 0:
                new_length = word_length
            else:
                new_length = current_length + 1 + word_length  # スペースを含む

            # 行の長さ制限をチェック
            if new_length <= max_chars_per_line:
                current_line.append(word)
                current_length = new_length
            else:
                # 現在の行を確定し、新しい行を開始
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length

        # 最後の行を追加
        if current_line:
            lines.append(' '.join(current_line))

        # 最大3行に制限
        if len(lines) > 3:
            # 3行を超える場合は最初の3行のみ使用
            lines = lines[:3]

        return '\n'.join(lines)

    def _create_rounded_rectangle(self, width: int, height: int, radius: int = 30):
        """角丸の長方形画像を作成"""
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [(0, 0), (width, height)],
            radius=radius,
            fill=(0, 0, 0, 128)  # 半透明の黒
        )

        return img

    def _add_subtitles_with_dynamic_bg(self, video_clip, subtitle_path: Path):
        """動的な背景付きで字幕を追加"""
        # SRTファイルをパース
        subtitles = self._parse_srt(subtitle_path)

        # すべてのクリップを格納
        all_clips = [video_clip]

        for start, end, text in subtitles:
            # テキストをフォーマット（改行を追加）
            formatted_text = self._format_subtitle_text(text)
            line_count = len(formatted_text.split('\n'))

            # 行数に応じて背景の高さを調整
            if line_count == 1:
                bg_height = 100  # 1行の場合
            elif line_count == 2:
                bg_height = 150  # 2行の場合
            else:  # 3行以上の場合
                bg_height = 200  # 3行の場合は200px

            # この字幕用の角丸背景を作成
            rounded_img = self._create_rounded_rectangle(1600, bg_height)
            img_array = np.array(rounded_img)

            # 背景クリップを作成
            bg_clip = ImageClip(img_array, duration=end-start)
            bg_clip = bg_clip.with_start(start).with_end(end)

            # 背景の位置
            bg_y_position = 750
            bg_clip = bg_clip.with_position(('center', bg_y_position))

            all_clips.append(bg_clip)

            # テキストクリップを作成
            txt_clip = TextClip(
                text=formatted_text,
                font_size=72,
                font='/System/Library/Fonts/Helvetica.ttc',
                color='white',
                method='caption',
                size=(1500, None),
                text_align='center'
            )

            # 時間を設定
            txt_clip = txt_clip.with_start(start).with_end(end)

            # テキストの位置（背景の真ん中により正確に配置）
            bg_center_y = bg_y_position + (bg_height // 2)

            if line_count == 1:
                txt_y_position = bg_center_y - 36  # フォントサイズの半分
            elif line_count == 2:
                txt_y_position = bg_center_y - 45  # 2行の場合
            else:  # 3行以上
                txt_y_position = bg_center_y - 55  # 3行の場合

            txt_clip = txt_clip.with_position(('center', txt_y_position))

            all_clips.append(txt_clip)

        # すべてのクリップを合成
        return CompositeVideoClip(all_clips)

    def _parse_srt(self, subtitle_path: Path) -> List[Tuple[float, float, str]]:
        """SRTファイルをパースして字幕データを取得"""
        subtitles = []

        with open(subtitle_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        blocks = content.split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                time_line = lines[1]
                start_time, end_time = time_line.split(' --> ')

                start_seconds = self._time_to_seconds(start_time)
                end_seconds = self._time_to_seconds(end_time)

                text = ' '.join(lines[2:])

                subtitles.append((start_seconds, end_seconds, text))

        return subtitles

    def _time_to_seconds(self, time_str: str) -> float:
        """SRT時間形式を秒に変換"""
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        hours = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def _create_simple_waveform(self, duration: float):
        """シンプルな音声波形バーを作成"""
        bars = []
        bar_width = 20
        bar_spacing = 10
        max_height = 60

        for i in range(5):
            height = np.random.randint(20, max_height)

            bar = ColorClip(
                size=(bar_width, height),
                color=(255, 255, 255),
                duration=duration
            )

            bar = bar.with_opacity(0.8)

            x = 1920 - 200 + i * (bar_width + bar_spacing)
            y = 880 - height // 2

            bar = bar.with_position((x, y))
            bars.append(bar)

        return CompositeVideoClip(bars)