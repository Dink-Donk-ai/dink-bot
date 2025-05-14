import os
from typing import Optional
from pydantic import validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    discord_token: str
    channel_id: int
    database_url: str

    @validator('discord_token')
    def validate_discord_token(cls, v):
        if not v:
            raise ValueError('Discord token must be provided')
        return v

    @validator('database_url')
    def validate_database_url(cls, v):
        if not v:
            raise ValueError('Database URL must be provided')
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError('Database URL must be a valid PostgreSQL URL')
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

try:
    settings = Settings()
except Exception as e:
    print(f"Failed to load configuration: {str(e)}")
    raise