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

    def _create_title_overlay(self, episode: Episode, duration: float, series_title: str = None):
        """タイトルオーバーレイを作成（PILを使用）"""
        print("Creating title overlay...")

        # カスタマイズ可能な設定
        TITLE_CONFIG = {
            'font_size': 62,
            'text_color': (255, 255, 255),  # RGB形式
            'margin_top': 57,
            'margin_left': 40,
            'position': 'top-left',
            'text_shadow': True,
            'shadow_style': 'thick',
            'shadow_offset': 2,
            'shadow_thickness': 3,
            'shadow_color': (0, 0, 0),  # RGB形式
            'shadow_opacity': 0.7,
            'padding': 30  # テキスト周りの余白
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

            print(f"Final title text: {repr(title_text)}")

            # PILでテキストを描画
            from PIL import ImageFont

            # フォントを試す
            font_paths = [
                '/System/Library/Fonts/Helvetica.ttc',
                '/System/Library/Fonts/Avenir Next.ttc',
                '/System/Library/Fonts/Avenir.ttc',
                '/System/Library/Fonts/HelveticaNeue.ttc',
            ]

            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, TITLE_CONFIG['font_size'])
                    print(f"Successfully loaded font: {font_path}")
                    break
                except:
                    continue

            if font is None:
                # デフォルトフォントを使用
                font = ImageFont.load_default()
                print("Using default font")

            # ダミー画像でテキストサイズを測定
            dummy_img = Image.new('RGBA', (1, 1), (0, 0, 0, 0))
            dummy_draw = ImageDraw.Draw(dummy_img)

            # textbboxを使用してテキストの境界ボックスを取得
            bbox = dummy_draw.textbbox((0, 0), title_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # パディングを含めた画像サイズ
            padding = TITLE_CONFIG['padding']
            img_width = text_width + padding * 2
            img_height = text_height + padding * 2

            print(f"Text size: {text_width}x{text_height}")
            print(f"Image size with padding: {img_width}x{img_height}")

            # 透明な画像を作成
            img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # 影を描画（thickスタイルの場合）
            if TITLE_CONFIG['text_shadow']:
                if TITLE_CONFIG['shadow_style'] == 'thick':
                    thickness = TITLE_CONFIG['shadow_thickness']
                    shadow_alpha = int(255 * TITLE_CONFIG['shadow_opacity'])

                    for i in range(thickness, 0, -1):
                        opacity = shadow_alpha * (1 - (i / (thickness * 2)))
                        shadow_color = TITLE_CONFIG['shadow_color'] + (int(opacity),)
                        draw.text(
                            (padding + i, padding + i),
                            title_text,
                            font=font,
                            fill=shadow_color
                        )
                else:
                    # 通常の影
                    shadow_alpha = int(255 * TITLE_CONFIG['shadow_opacity'])
                    shadow_color = TITLE_CONFIG['shadow_color'] + (shadow_alpha,)
                    offset = TITLE_CONFIG['shadow_offset']
                    draw.text(
                        (padding + offset, padding + offset),
                        title_text,
                        font=font,
                        fill=shadow_color
                    )

            # メインテキストを描画
            text_color = TITLE_CONFIG['text_color'] + (255,)  # 完全不透明
            draw.text(
                (padding, padding),
                title_text,
                font=font,
                fill=text_color
            )

            # numpy配列に変換
            img_array = np.array(img)

            # ImageClipを作成
            title_clip = ImageClip(img_array, duration=duration)

            # 位置を設定
            if TITLE_CONFIG['position'] == 'top-left':
                clip_x = TITLE_CONFIG['margin_left']
                clip_y = TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'top-right':
                clip_x = 1920 - img_width - TITLE_CONFIG['margin_left']
                clip_y = TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'bottom-left':
                clip_x = TITLE_CONFIG['margin_left']
                clip_y = 1080 - img_height - TITLE_CONFIG['margin_top']
            elif TITLE_CONFIG['position'] == 'bottom-right':
                clip_x = 1920 - img_width - TITLE_CONFIG['margin_left']
                clip_y = 1080 - img_height - TITLE_CONFIG['margin_top']
            else:
                clip_x = TITLE_CONFIG['margin_left']
                clip_y = TITLE_CONFIG['margin_top']

            title_clip = title_clip.with_position((int(clip_x), int(clip_y)))

            print(f"Title clip position: ({clip_x}, {clip_y})")
            print("Title overlay created successfully with PIL")

            return title_clip

        except Exception as e:
            print(f"FATAL ERROR in title overlay creation: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _get_subtitle_clips_list(self, subtitle_path: Path) -> List:
        """字幕クリップのリストを返す（CompositeVideoClipではなく個別のクリップのリスト）"""
        subtitles = self._parse_srt(subtitle_path)
        clips = []

        # 調整可能な定数
        VERTICAL_PADDING = 20      # 字幕背景の上下余白（削減）
        HORIZONTAL_PADDING = 60    # 字幕背景の左右余白（削減）
        LINE_HEIGHT = 65           # 行の高さ（削減）
        LINE_SPACING = 3           # 行間（削減）
        SCREEN_HEIGHT = 1080
        BOTTOM_MARGIN = 40         # 画面下端からの最小マージン
        MAX_LINES = 4              # 最大行数制限

        for start, end, text in subtitles:
            formatted_text = self._format_subtitle_text(text, max_lines=MAX_LINES)
            lines = formatted_text.split('\n')
            line_count = len(lines)

            # Skip empty text
            if not formatted_text.strip():
                print(f"WARNING: Skipping empty subtitle at {start}-{end}")
                continue

            # 背景サイズを計算
            content_height = (line_count * LINE_HEIGHT) + ((line_count - 1) * LINE_SPACING)
            bg_height = content_height + (VERTICAL_PADDING * 2)
            bg_width = 1400 + (HORIZONTAL_PADDING * 2)  # 幅も調整

            # Ensure minimum dimensions
            bg_height = max(bg_height, 50)
            bg_width = max(bg_width, 100)

            # 表示位置を動的に調整（4行以上の場合は上に移動）
            if line_count <= 3:
                bg_y_position = 750
            else:
                # 4行の場合は少し上に配置
                max_allowed_y = SCREEN_HEIGHT - bg_height - BOTTOM_MARGIN
                bg_y_position = min(700, max_allowed_y)

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

            # 各行を配置（フォントサイズも調整）
            for i, line in enumerate(lines):
                if not line.strip():  # Skip empty lines
                    continue

                try:
                    # 行数に応じてフォントサイズを調整
                    if line_count <= 2:
                        font_size = 72
                    elif line_count == 3:
                        font_size = 68
                    else:  # 4行
                        font_size = 64

                    line_clip = TextClip(
                        text=line.strip(),
                        font_size=font_size,
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

                    # テキストの垂直位置を調整
                    line_y = (bg_y_position +
                              VERTICAL_PADDING +
                              (i * (LINE_HEIGHT + LINE_SPACING)) +
                              (LINE_HEIGHT // 2) - (font_size // 2))

                    line_clip = line_clip.with_position(('center', line_y))
                    clips.append(line_clip)

                except Exception as e:
                    print(f"ERROR creating text clip for line '{line}': {e}")
                    continue

        return clips

    def _format_subtitle_text(self, text: str, max_chars_per_line: int = 45, max_lines: int = 4) -> str:
        """長いテキストを適切に改行（最大行数を指定可能）"""
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

                # 最大行数に達した場合は残りを省略
                if len(lines) >= max_lines - 1:
                    # 残りの単語を最後の行に詰め込む
                    remaining_words = words[words.index(word):]
                    last_line = ' '.join(remaining_words)
                    # 最後の行が長すぎる場合は省略記号を追加
                    if len(last_line) > max_chars_per_line + 10:
                        last_line = last_line[:max_chars_per_line] + '...'
                    lines.append(last_line)
                    break

        # 最後の行を追加（最大行数に達していない場合）
        if current_line and len(lines) < max_lines:
            lines.append(' '.join(current_line))

        # 最大行数制限
        if len(lines) > max_lines:
            lines = lines[:max_lines]

        return '\n'.join(lines)