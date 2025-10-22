from functools import lru_cache
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class AppSettings(BaseSettings):
    """
    Application configuration class for loading environment variables using Pydantic Settings.

    Fields:
        app_name (str): The name of the application.
        owner (str): Owner/maintainer of the application.
        email (str): Contact email.
    """

    # model_config = SettingsConfigDict(env_file=str(env_path), extra="ignore")

    # Static App Info
    app_name: str = "Multilingual Transcriber"
    owner: str = "Naveen Gurram"
    email: str = "getsnaveen@gmail.com"

    openai_key: str
    google_translate_key: str
    google_credentials_path: str
    gemini_key: str

    input_movie_path: str
    input_audio_path: str
    languages_to_convert: List[str]
    segment_length: int
        
    elevenlabs_key: str
    elevenlabs_url: str
    elevenlabs_modelid: str
    
    aws_access_key:str
    aws_secret_key:str
    aws_region:str
    s3_bucket_name:str
    
    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> AppSettings:
    """
    Returns a singleton instance of AppSettings loaded from the .env file.
    Uses LRU caching to prevent reloading on each access.

    Returns:
        AppSettings: A cached instance of the configuration object.
    """
    return AppSettings()

# if __name__ == "__main__":
#     settings = get_settings()
#     print(settings.model_dump())
