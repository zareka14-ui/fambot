import os
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

@dataclass
class Config:
    bot_token: str
    admin_ids: list[int]

def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN"),
        admin_ids=[int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
    )

config = load_config()