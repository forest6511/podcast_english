import click
import json
from pathlib import Path
from rich.console import Console

from .models.series import Series
from .utils.path_manager import PathManager
from .generators.audio_generator import AudioGenerator
from .generators.subtitle_generator import SubtitleGenerator
from .generators.video_generator import VideoGenerator

console = Console()

@click.command()
@click.option('--series', '-s', required=True, help='Series ID (e.g., 001)')
@click.option('--episode', '-e', help='Specific episode ID (optional)')
@click.option('--keep-existing', is_flag=True, help='Keep existing output files')
def main(series, episode, keep_existing):
    """Generate podcast videos"""

    console.print(f"[bold blue]English Podcast Generator[/bold blue]")
    console.print(f"Series: {series}")

    # パス管理
    pm = PathManager(series)

    # series.json を読み込み
    if not pm.series_json.exists():
        console.print(f"[red]Error: {pm.series_json} not found![/red]")
        return

    with open(pm.series_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Pydanticモデルに変換
    series_data = Series(**data)

    # 出力ディレクトリをクリーン
    if not keep_existing:
        console.print("[yellow]Cleaning output directory...[/yellow]")
        pm.clean_output()

    # ジェネレーターを初期化
    audio_gen = AudioGenerator(series_data.settings, pm)
    subtitle_gen = SubtitleGenerator(series_data.settings, pm)
    video_gen = VideoGenerator(series_data.settings, pm)

    # エピソードを処理
    episodes_to_process = series_data.episodes
    if episode:
        episodes_to_process = [ep for ep in episodes_to_process if ep.id == episode]

    for ep in episodes_to_process:
        console.print(f"\n[green]Processing Episode {ep.id}: {ep.title}[/green]")

        try:
            # 音声生成
            console.print("1. Generating audio...")
            audio_path = audio_gen.generate_episode_audio(ep)

            # 字幕生成
            console.print("2. Generating subtitles...")
            subtitle_path = subtitle_gen.generate_subtitles(ep, audio_path)

            # 動画生成
            console.print("3. Generating video...")
            video_path = video_gen.generate_video(ep, audio_path, subtitle_path)

            console.print(f"[bold green]✓ Complete: {video_path}[/bold green]")

        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()