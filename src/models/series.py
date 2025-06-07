from pydantic import BaseModel
from typing import List, Dict, Optional

class Voice(BaseModel):
    name: str  # Google Cloud TTSの音声名

class Settings(BaseModel):
    tts_engine: str = "google-cloud"
    speaking_speed: float = 0.9
    pause_between_lines: float = 1.5
    background_image: str = "assets/backgrounds/podcast_bg.jpg"
    voices: Dict[str, Voice]

class Conversation(BaseModel):
    speaker: str
    text: str

class Episode(BaseModel):
    id: str
    title: str
    description: str
    duration_estimate: int
    conversations: List[Conversation]

class SeriesInfo(BaseModel):
    id: str
    title: str
    subtitle: str
    description: str
    target_level: str
    status: str

class Series(BaseModel):
    series_info: SeriesInfo
    settings: Settings
    episodes: List[Episode]