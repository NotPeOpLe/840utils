import sys
from typing import Optional
from pydantic import BaseSettings


class Configuration(BaseSettings):
    debug: Optional[bool] = False
    db_url: str
    osu_client_id: int
    osu_client_secret: str
    osu_client_redirect_uri: str

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


config = Configuration(
    _env_file=('.env', '.env.local')['--debug' in sys.argv]
)
