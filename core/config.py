import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Exchange
    EXCHANGE_ID: str = "binance"
    EXCHANGE_API_KEY: str = ""
    EXCHANGE_SECRET: str = ""
    USE_TESTNET: bool = True

    # AI
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "gpt-oss-120b" # Or specific model provided by user

    # News
    CRYPTO_PANIC_API_KEY: str = ""
    NEWS_API_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""

    # Security
    WEBHOOK_PASSPHRASE: str = "changeme"

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    ENABLE_TELEGRAM: bool = False

    # Scanning
    WATCH_SYMBOLS: str = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT"
    SCAN_INTERVAL_MINUTES: int = 15
    FIB_TOLERANCE: float = 0.015 # 1.5% sensitivity
    SENTIMENT_BREAKOUT_THRESHOLD: float = 0.8
    MOMENTUM_SENTIMENT_THRESHOLD: float = 0.92
    MOMENTUM_EMA_GAP: float = 0.01 # 1% above EMA

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
