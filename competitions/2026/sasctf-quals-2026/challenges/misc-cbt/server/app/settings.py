from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SSH_")

    bind: str = "0.0.0.0"
    port: int = 2222
    username: str = "lame"
    password: str = "password"
    banner: str = "SSH-2.0-OpenSSH_9.7"
    hostkey_dir: Path = Path("/app/hostkeys")

    flag: str = "SAS{example_flag}"
    pass_pow_phrase: str = "s3cr3t-4Dmin-1337!"

    rsa_key_bits: int = 3072
    listen_backlog: int = 100
    recv_buffer_size: int = 1024
    work_queue_timeout: float = 0.5
    pow_bits: int = 30

    database_url: str = "postgresql+psycopg://schizo:schizo@postgres:5432/schizo"
    llm_base_url: str
    llm_api_key: str
    llm_model: str = "MiniMaxAI/MiniMax-M2.7"
    hostname: str = "alpine"
    initial_cwd: str = "/home/lame"
    max_commands: int = 15
    max_input_chars: int = 1500
    max_output_tokens_per_command: int = 3000


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
