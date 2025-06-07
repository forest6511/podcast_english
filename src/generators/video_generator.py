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

    def _format_subtitle_text(self, text: str, max_chars_per_line: int = 40) -> str:
        """長いテキストを適切に改行（最大4行）"""
        words = text.split()

        # 短いテキストはそのまま返す
        if len(text) <= 50:
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

        # 最大4行に制限（3行から4行に変更）
        if len(lines) > 4:
            lines = lines[:4]

        return '\n'.join(lines)

    def _add_subtitles_with_dynamic_bg(self, video_clip, subtitle_path: Path):
        """スマートロジック：画面内に収まるよう動的調整"""
        subtitles = self._parse_srt(subtitle_path)
        all_clips = [video_clip]

        # 定数
        VERTICAL_PADDING = 25
        LINE_HEIGHT = 80
        LINE_SPACING = 5
        SCREEN_HEIGHT = 1080
        BOTTOM_MARGIN = 50  # 画面下端からの最小マージン

        for start, end, text in subtitles:
            formatted_text = self._format_subtitle_text(text)
            lines = formatted_text.split('\n')
            line_count = len(lines)

            # 背景サイズを計算
            content_height = (line_count * LINE_HEIGHT) + ((line_count - 1) * LINE_SPACING)
            bg_height = content_height + (VERTICAL_PADDING * 2)

            # 表示位置を動的に調整
            max_allowed_y = SCREEN_HEIGHT - bg_height - BOTTOM_MARGIN
            bg_y_position = min(750, max_allowed_y)  # 通常は750、はみ出る場合は上に移動

            # 背景作成
            rounded_img = self._create_rounded_rectangle(1600, bg_height)
            img_array = np.array(rounded_img)

            bg_clip = ImageClip(img_array, duration=end-start)
            bg_clip = bg_clip.with_start(start).with_end(end)
            bg_clip = bg_clip.with_position(('center', bg_y_position))
            all_clips.append(bg_clip)

            # 各行を配置
            for i, line in enumerate(lines):
                line_clip = TextClip(
                    text=line,
                    font_size=72,
                    font='/System/Library/Fonts/Helvetica.ttc',
                    color='white',
                    method='label',
                    text_align='center'
                )

                line_clip = line_clip.with_start(start).with_end(end)

                line_y = (bg_y_position +
                          VERTICAL_PADDING +
                          (i * (LINE_HEIGHT + LINE_SPACING)) +
                          (LINE_HEIGHT // 2) - 36)

                line_clip = line_clip.with_position(('center', line_y))
                all_clips.append(line_clip)

        return CompositeVideoClip(all_clips)