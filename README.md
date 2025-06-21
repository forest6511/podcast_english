# English Podcast Generator

Automated English learning podcast video generator with text-to-speech and subtitles.

## Setup

```bash
# Install dependencies
poetry install
```

# Activate virtual environment
```bash
poetry shell
```
# Run generator
```
poetry run python -m src.main --series 001
poetry run python -m src.main --series 002

```
Project Structure

```
data/series/ - Input JSON files
output/series/ - Generated videos, audio, and subtitles
assets/ - Static resources (backgrounds, fonts)
src/ - Source code
```
Features

```
Automated TTS using Google Text-to-Speech
Subtitle generation
Video composition with MoviePy
Se```ries-based content management
```

```
以下のトピックで英語学習Podcast用の会話を作成してください。

【トピック】
[具体的なテーマを記入]

【含めてほしい場面・フレーズ】
- [場面1]
- [場面2]
- [場面3]

【出力形式】
- 既存のJSON形式に従う
- episodeのidは[番号]
- タイトルとsubtitleは視聴者の興味を引くものに

【TTS最適化】
- "..."は自然な文章に変更
- 感嘆符の連続使用を避ける
- 不自然な記号を除去
- "Ha!"は"Haha"または削除
```