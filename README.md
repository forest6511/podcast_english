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
poetry run python -m src.main generate --series 001
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


TTS用に最適化した版を作成します。

"..." → 自然な文章に変更
"Ha!" → "Haha" または削除
感嘆符の連続使用を避ける
不自然な記号を除去
