import os
from typing import Optional
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Required environment variables:
    - DISCORD_BOT_TOKEN: Your Discord bot token
    - DISCORD_CHANNEL_ID: The Discord channel ID where the bot will operate
    - DATABASE_URL: PostgreSQL connection URL (provided by Railway)
    - DISCORD_WEBHOOK_URL: Discord webhook URL for notifications
    """
    discord_token: str = Field(alias='DISCORD_BOT_TOKEN')
    channel_id: int = Field(alias='DISCORD_CHANNEL_ID')
    database_url: str = Field(alias='DATABASE_URL')
    webhook_url: str = Field(alias='DISCORD_WEBHOOK_URL')

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

    @field_validator('discord_token')
    @classmethod
    def validate_token(cls, v):
        if not v:
            raise ValueError('DISCORD_BOT_TOKEN environment variable is required')
        return v

    @field_validator('channel_id')
    @classmethod
    def validate_channel(cls, v):
        if not v:
            raise ValueError('DISCORD_CHANNEL_ID environment variable is required')
        return v

    @field_validator('webhook_url')
    @classmethod
    def validate_webhook(cls, v):
        if not v:
            raise ValueError('DISCORD_WEBHOOK_URL environment variable is required')
        return v

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v):
        if not v:
            raise ValueError('DATABASE_URL environment variable is required')
        if not v.startswith(('postgresql://', 'postgres://')):
            raise ValueError('DATABASE_URL must be a valid PostgreSQL URL')
        return v

try:
    settings = Settings()
except Exception as e:
    print("\nConfiguration Error:")
    print("===================")
    print("Please make sure the following environment variables are set in Railway:")
    print("1. DISCORD_BOT_TOKEN - Your Discord bot token")
    print("2. DISCORD_CHANNEL_ID - The Discord channel ID")
    print("3. DISCORD_WEBHOOK_URL - The Discord webhook URL")
    print("4. DATABASE_URL - PostgreSQL connection URL (should be set automatically)")
    print("\nDetailed error:")
    print(str(e))
    raise