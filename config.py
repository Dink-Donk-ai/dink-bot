import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    discord_token: str
    channel_id: int
    database_url: str

    class Config:
        env_file = ".env"

settings = Settings()