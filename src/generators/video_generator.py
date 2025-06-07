from pathlib import Path
from moviepy import VideoFileClip, ImageClip, AudioFileClip, CompositeVideoClip, ColorClip, TextClip
import numpy as np
from typing import List, Tuple
from PIL import Image, ImageDraw

from ..models.series import Episode, Settings
from ..utils.path_manager import PathManager

class VideoGenerator:
    def __init__(self, settings: Settings, path_manager: PathManager):
        self.settings = settings
        self.pm = path_manager

    def _validate_clip(self, clip, name="clip"):
        """Validate clip dimensions to prevent broadcasting errors"""
        if hasattr(clip, 'size'):
            width, height = clip.size
            if width <= 0 or height <= 0:
                print(f"ERROR: {name} has invalid dimensions: {width}x{height}")
                return False
        return True

    def generate_video(self, episode: Episode, audio_path: Path, subtitle_path: Path, series_title: str = None) -> Path:
        """動画を生成"""
        print(f"Generating video for episode {episode.id}: {episode.title}")

        # 音声を読み込み
        audio_clip = AudioFileClip(str(audio_path))
        duration = audio_clip.duration

        # 背景画像を読み込み
        background_path = self.pm.get_background_path()
        background = ImageClip(str(background_path), duration=duration)
        background = background.resized((1920, 1080))

        if not self._validate_clip(background, "background"):
            raise ValueError("Invalid background clip dimensions")

        # すべてのクリップを一つのリストに集める
        all_clips = [background]  # 最背面

        # 字幕クリップを個別に追加
        try:
            subtitle_clips = self._get_subtitle_clips_list(subtitle_path)
            all_clips.extend(subtitle_clips)  # 中間層
            print(f"Added {len(subtitle_clips)} subtitle clips")
        except Exception as e:
            print(f"ERROR in subtitle processing: {e}")
            import traceback
            traceback.print_exc()

        # タイトルクリップを取得
        title_result = self._create_title_overlay(episode, duration, series_title)

        # CompositeVideoClipの場合は展開、そうでない場合はそのまま追加
        if isinstance(title_result, CompositeVideoClip):
            # CompositeVideoClipの中身を展開して追加
            for clip in title_result.clips:
                all_clips.append(clip)
            print(f"Added {len(title_result.clips)} title clips (shadow + text)")
        else:
            # 単一のクリップの場合
            all_clips.append(title_result)
            print("Added single title clip")

        print(f"Total clips for composition: {len(all_clips)}")

        # 最終合成
        final_video_clips = CompositeVideoClip(all_clips)

        # 音声を設定
        final_video = final_video_clips.with_audio(audio_clip)

        # 出力
        output_path = self.pm.get_video_path(episode.id, episode.title)
        final_video.write_videofile(
            str(output_path),
            fps=24,
            codec='libx264',
            audio_codec='aac',
            threads=4
        )

        audio_clip.close()
        final_video.close()

        print(f"Video saved to: {output_path}")
        return output_path

    def _get_subtitle_clips_list(self, subtitle_path: Path) -> List:
        """字幕クリップのリストを返す（CompositeVideoClipではなく個別のクリップのリスト）"""
        subtitles = self._parse_srt(subtitle_path)
        clips = []

        # 調整可能な定数
        VERTICAL_PADDING = 25      # 字幕背景の上下余白
        HORIZONTAL_PADDING = 80    # 字幕背景の左右余白
        LINE_HEIGHT = 80           # 行の高さ
        LINE_SPACING = 5           # 行間
        SCREEN_HEIGHT = 1080
        BOTTOM_MARGIN = 50         # 画面下端からの最小マージン

        for start, end, text in subtitles:
            formatted_text = self._format_subtitle_text(text)
            lines = formatted_text.split('\n')
            line_count = len(lines)

            # Skip empty text
            if not formatted_text.strip():
                print(f"WARNING: Skipping empty subtitle at {start}-{end}")
                continue

            # 背景サイズを計算
            content_height = (line_count * LINE_HEIGHT) + ((line_count - 1) * LINE_SPACING)
            bg_height = content_height + (VERTICAL_PADDING * 2)
            bg_width = 1600 + (HORIZONTAL_PADDING * 2)  # 調整可能な幅

            # Ensure minimum dimensions
            bg_height = max(bg_height, 50)
            bg_width = max(bg_width, 100)

            # 表示位置を動的に調整
            max_allowed_y = SCREEN_HEIGHT - bg_height - BOTTOM_MARGIN
            bg_y_position = min(750, max_allowed_y)  # 通常は750、はみ出る場合は上に移動

            # 背景作成
            try:
                rounded_img = self._create_rounded_rectangle(bg_width, bg_height)
                img_array = np.array(rounded_img)

                # Validate image array
                if img_array.size == 0:
                    print(f"WARNING: Empty background image for subtitle: {text[:50]}...")
                    continue

                bg_clip = ImageClip(img_array, duration=end-start)
                bg_clip = bg_clip.with_start(start).with_end(end)
                bg_clip = bg_clip.with_position(('center', bg_y_position))

                # Validate background clip
                if not self._validate_clip(bg_clip, "subtitle background"):
                    print(f"WARNING: Invalid background clip for subtitle: {text[:50]}...")
                    continue

                clips.append(bg_clip)
            except Exception as e:
                print(f"ERROR creating background for subtitle '{text[:50]}...': {e}")
                continue

            # 各行を配置
            for i, line in enumerate(lines):
                if not line.strip():  # Skip empty lines
                    continue

                try:
                    line_clip = TextClip(
                        text=line.strip(),
                        font_size=72,
                        font='/System/Library/Fonts/Helvetica.ttc',
                        color='white',
                        method='label',
                        text_align='center'
                    )

                    # Validate text clip dimensions
                    if not self._validate_clip(line_clip, f"text line: {line[:20]}"):
                        print(f"WARNING: Invalid text clip for line: {line}")
                        continue

                    line_clip = line_clip.with_start(start).with_end(end)

                    line_y = (bg_y_position +
                              VERTICAL_PADDING +
                              (i * (LINE_HEIGHT + LINE_SPACING)) +
                              (LINE_HEIGHT // 2) - 36)

                    line_clip = line_clip.with_position(('center', line_y))
                    clips.append(line_clip)

                except Exception as e:
                    print(f"ERROR creating text clip for line '{line}': {e}")
                    continue

        return clips

    def _create_rounded_rectangle(self, width: int, height: int, radius: int = 30):
        """角丸の長方形画像を作成"""
        # Ensure minimum dimensions
        width = max(width, 10)
        height = max(height, 10)
        radius = min(radius, min(width, height) // 2)

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

    def _format_subtitle_text(self, text: str, max_chars_per_line: int = 40) -> str:
        """長いテキストを適切に改行（最大6行）"""
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

        # 最大行数制限を6行に拡張
        if len(lines) > 6:
            lines = lines[:6]

        return '\n'.join(lines)

    def _create_title_overlay(self, episode: Episode, duration: float, series_title: str = None):
        """タイトルオーバーレイを作成"""
        print("Creating title overlay...")

        # カスタマイズ可能な設定
        TITLE_CONFIG = {
            'font_size':52,
            'text_color': 'white',
            'margin_top': 69,          # 上マージン
            'margin_left': 40,         # 左マージン
            'position': 'top-left',    # 'top-left', 'top-right', 'bottom-left', 'bottom-right'
            'text_shadow': True,       # テキストに影をつけるかどうか
            'shadow_offset': 2,        # 影のオフセット
            'shadow_color': 'black',   # 影の色
            'use_background': False,   # 背景を使用するかどうか
            'background_color': (0, 0, 0, 180),  # 半透明の黒背景
            'background_padding': 20   # 背景のパディング
        }

        try:
            # タイトルテキストを決定
            if series_title:
                title_text = series_title
                print(f"Using provided series title: {title_text}")
            elif hasattr(episode, 'series_info') and episode.series_info and hasattr(episode.series_info, 'title'):
                title_text = episode.series_info.title
                print(f"Using series title from episode: {title_text}")
            else:
                title_text = "Untitled Series"
                print("Using fallback title: Untitled Series")

            # 長いタイトルの場合は改行
            if len(title_text) > 25:
                words = title_text.split()
                lines = []
                current_line = []
                current_length = 0

                for word in words:
                    if current_length + len(word) + 1 <= 25:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                        current_length = len(word)

                if current_line:
                    lines.append(' '.join(current_line))

                title_text = '\n'.join(lines[:2])  # 最大2行

            print(f"Final title text: {repr(title_text)}")

            # タイトルクリップを作成
            title_fonts = [
                '/System/Library/Fonts/Avenir Next.ttc',
                '/System/Library/Fonts/Avenir.ttc',
                '/System/Library/Fonts/HelveticaNeue.ttc',
                '/System/Library/Fonts/Helvetica.ttc',
            ]

            title_clip = None
            for font in title_fonts:
                try:
                    title_clip = TextClip(
                        text=title_text,
                        font_size=TITLE_CONFIG['font_size'],
                        font=font,
                        color=TITLE_CONFIG['text_color'],
                        method='label',
                        text_align='left'
                    )
                    print(f"Successfully using font: {font}")
                    print(f"Title clip size: {title_clip.size}")
                    break
                except Exception as e:
                    print(f"Font {font} failed: {e}")
                    continue

            # フォールバック
            if title_clip is None:
                title_clip = TextClip(
                    text=title_text,
                    font_size=TITLE_CONFIG['font_size'],
                    color=TITLE_CONFIG['text_color'],
                    method='label',
                    text_align='left'
                )
                print("Using system default font")

            # Validate title clip
            if not self._validate_clip(title_clip, "title text"):
                raise ValueError("Title clip has invalid dimensions")

            title_clip = title_clip.with_duration(duration)

            # 位置を計算
            title_width, title_height = title_clip.size

            if TITLE_CONFIG['position'] == 'top-left':
                text_x = TITLE_CONFIG['margin_left']
                text_y = TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'top-right':
                text_x = 1920 - title_width - TITLE_CONFIG['margin_left']
                text_y = TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'bottom-left':
                text_x = TITLE_CONFIG['margin_left']
                text_y = 1080 - title_height - TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'bottom-right':
                text_x = 1920 - title_width - TITLE_CONFIG['margin_left']
                text_y = 1080 - title_height - TITLE_CONFIG['margin_top']
            else:
                text_x = TITLE_CONFIG['margin_left']
                text_y = TITLE_CONFIG['margin_top']

            # 画面外に出ないように調整
            text_x = max(0, min(text_x, 1920 - title_width))
            text_y = max(0, min(text_y, 1080 - title_height))

            print(f"Text position: ({text_x}, {text_y})")

            # タイトルテキストの位置を設定
            title_clip = title_clip.with_position((int(text_x), int(text_y)))

            # 影付きテキストを作成（CompositeVideoClipを使わない）
            if TITLE_CONFIG['text_shadow']:
                # 影のテキストを作成
                shadow_clip = None
                for font in title_fonts:
                    try:
                        shadow_clip = TextClip(
                            text=title_text,
                            font_size=TITLE_CONFIG['font_size'],
                            font=font,
                            color=TITLE_CONFIG['shadow_color'],
                            method='label',
                            text_align='left'
                        )
                        break
                    except:
                        continue

                if shadow_clip is None:
                    shadow_clip = TextClip(
                        text=title_text,
                        font_size=TITLE_CONFIG['font_size'],
                        color=TITLE_CONFIG['shadow_color'],
                        method='label',
                        text_align='left'
                    )

                shadow_clip = shadow_clip.with_duration(duration)
                shadow_x = text_x + TITLE_CONFIG['shadow_offset']
                shadow_y = text_y + TITLE_CONFIG['shadow_offset']
                shadow_clip = shadow_clip.with_position((int(shadow_x), int(shadow_y)))

                # 半透明の黒い影を作成（より自然な影）
                shadow_clip = shadow_clip.with_opacity(0.5)

                # 影とテキストを合成
                final_clip = CompositeVideoClip([shadow_clip, title_clip])
            else:
                # 影なしの場合は単純にタイトルクリップを返す
                final_clip = title_clip

            print("Title overlay created successfully")
            return final_clip

        except Exception as e:
            print(f"FATAL ERROR in title overlay creation: {e}")
            import traceback
            traceback.print_exc()
            raise