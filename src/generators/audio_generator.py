import os
import base64
import hashlib
import requests
import time
from pathlib import Path
from pydub import AudioSegment
from typing import List, Tuple
from dotenv import load_dotenv

from ..models.series import Series, Episode, Settings
from ..utils.path_manager import PathManager

# 環境変数をロード
load_dotenv()

class AudioGenerator:
    def __init__(self, settings: Settings, path_manager: PathManager):
        self.settings = settings
        self.pm = path_manager
        self.api_key = os.environ.get('GOOGLE_TTS_API_KEY')

        if not self.api_key:
            raise ValueError("GOOGLE_TTS_API_KEY 環境変数が設定されていません")

        # キャッシュディレクトリ
        self.cache_dir = self.pm.root / "cache" / "tts"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate_episode_audio(self, episode: Episode) -> Path:
        """エピソードの音声を生成"""
        print(f"Generating audio for episode {episode.id}: {episode.title}")

        audio_segments = []

        # 各会話の音声を生成
        for idx, conv in enumerate(episode.conversations):
            audio_path = self._generate_single_audio(
                episode.id, conv.speaker, conv.text, idx
            )

            # 音声を読み込み
            audio = AudioSegment.from_mp3(audio_path)
            audio_segments.append(audio)

            # 会話間の無音を追加（最後の会話以外）
            if idx < len(episode.conversations) - 1:
                silence = AudioSegment.silent(
                    duration=int(self.settings.pause_between_lines * 1000)
                )
                audio_segments.append(silence)

        # すべての音声を結合
        combined_audio = sum(audio_segments)

        # 結合した音声を保存
        output_path = self.pm.get_combined_audio_path(episode.id)
        combined_audio.export(output_path, format="mp3")

        print(f"Combined audio saved to: {output_path}")
        return output_path

    def _generate_single_audio(self, episode_id: str, speaker: str, text: str, line_num: int) -> Path:
        """単一の音声を生成（Google TTS API使用）"""
        output_path = self.pm.get_audio_path(episode_id, speaker, line_num)

        # 既存ファイルがあればスキップ
        if output_path.exists():
            print(f"Audio already exists: {output_path}")
            return output_path

        # キャッシュをチェック
        cache_path = self._get_cache_path(text, speaker)
        if cache_path.exists():
            print(f"Using cached audio: {cache_path}")
            # キャッシュから出力パスにコピー
            with open(cache_path, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())
            return output_path

        # 音声設定を取得（Pydanticモデルのアクセス方法を修正）
        voice_config = self.settings.voices.get(speaker, {})
        # voice_configはVoiceオブジェクトなので、属性として直接アクセス
        voice_name = voice_config.name if voice_config else 'en-US-Standard-F'

        # APIを使用して音声生成
        print(f"Generating: {speaker} - {text[:30]}...")
        audio_content = self._call_tts_api(text, voice_name)

        if audio_content:
            # キャッシュに保存
            with open(cache_path, "wb") as cache_file:
                cache_file.write(audio_content)

            # 出力ファイルに保存
            with open(output_path, "wb") as out_file:
                out_file.write(audio_content)

            # API制限対策
            time.sleep(0.1)

        return output_path

    def _get_cache_path(self, text: str, speaker: str) -> Path:
        """キャッシュファイルのパスを生成"""
        cache_key = hashlib.md5(f"{text}_{speaker}".encode('utf-8')).hexdigest()
        return self.cache_dir / f"{cache_key}.mp3"

    def _call_tts_api(self, text: str, voice_name: str) -> bytes:
        """Google TTS APIを呼び出して音声を生成"""
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"

        # 言語コードを抽出
        language_code = "-".join(voice_name.split("-")[:2])

        # SSMLを生成
        ssml_text = f"<speak>{text}</speak>"

        # スピード調整が必要な場合
        if self.settings.speaking_speed != 1.0:
            rate_percent = int(self.settings.speaking_speed * 100)
            ssml_text = f'<speak><prosody rate="{rate_percent}%">{text}</prosody></speak>'

        # APIリクエストデータ
        request_data = {
            "input": {"ssml": ssml_text},
            "voice": {
                "languageCode": language_code,
                "name": voice_name,
                "ssmlGender": "FEMALE" if "F" in voice_name else "MALE"
            },
            "audioConfig": {
                "audioEncoding": "MP3",
                "sampleRateHertz": 48000,
                "effectsProfileId": ["headphone-class-device"]
            }
        }

        # APIリクエスト送信
        response = requests.post(url, json=request_data)

        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

        # Base64デコード
        audio_content = base64.b64decode(response.json().get("audioContent", ""))
        return audio_content