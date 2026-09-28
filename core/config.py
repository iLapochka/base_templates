from enum import StrEnum
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_API_KEY = 'change-me'
MIN_API_KEY_LENGTH = 32


class Environment(StrEnum):
    """Runtime environment variants."""

    LOCAL = 'local'
    PRODUCTION = 'production'


class Config(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    ENVIRONMENT: Environment = Environment.LOCAL

    # The single credential every endpoint but /health is checked against.
    API_KEY: str = LOCAL_API_KEY

    # The one operator of /admin. No password or no secret, and /admin is not mounted at all.
    ADMIN_USERNAME: str = 'admin'
    ADMIN_PASSWORD: str = ''
    ADMIN_SECRET_KEY: str = ''

    # sqlite+aiosqlite:///./local.db  OR  postgresql+asyncpg://...
    DATABASE_URL: str = 'sqlite+aiosqlite:///./local.db'

    # Downloaded sources and rendered results live here; the database keeps only their paths.
    MEDIA_DIR: Path = Path('media')

    FFMPEG_BINARY: str = 'ffmpeg'
    FFPROBE_BINARY: str = 'ffprobe'
    # A render that has not finished by then is killed and the job is marked failed.
    VIDEO_JOB_TIMEOUT_SECONDS: int = 900
    # ffmpeg takes every core it sees; more than this many renders at once and the box stalls.
    VIDEO_MAX_CONCURRENT_JOBS: int = 2
    # A download larger than this is refused before it fills the disk.
    VIDEO_MAX_DOWNLOAD_MEGABYTES: int = 1024

    @property
    def is_local(self) -> bool:
        """Return True when running in the local development environment."""
        return self.ENVIRONMENT == Environment.LOCAL

    @model_validator(mode='after')
    def require_a_real_api_key(self) -> 'Config':
        """An empty key matches an empty header; the default one is known to everybody."""
        if not self.API_KEY:
            raise ValueError('API_KEY must not be empty.')
        if not self.is_local and (
            self.API_KEY == LOCAL_API_KEY or len(self.API_KEY) < MIN_API_KEY_LENGTH
        ):
            raise ValueError(
                f'API_KEY outside local must be a random value of at least {MIN_API_KEY_LENGTH} '
                'characters, e.g. `openssl rand -hex 32`.',
            )
        return self


config: Config = Config()
