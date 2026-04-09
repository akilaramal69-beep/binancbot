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
    SENTIMENT_ENTRY_THRESHOLD: float = 0.85
    SENTIMENT_BREAKOUT_THRESHOLD: float = 0.88
    MOMENTUM_SENTIMENT_THRESHOLD: float = 0.92
    MOMENTUM_EMA_GAP: float = 0.01 # 1% above EMA
    FAST_TRADE_MODE: bool = False # Lowers the score threshold to 5 and widens EMA tolerance
    
    # Risk Management
    MAX_CONCURRENT_POSITIONS: int = 3
    MAX_HOLDING_HOURS: int = 24
    MARKET_REGIME_EMA_PERIOD: int = 200 # EMA for trend detection
    
    # Trading Mode - Standardize trade type
    TRADING_MODE: str = "scalping"  # "scalping" or "swing"
    RISK_PER_TRADE_PERCENT: float = 0.01  # 1% risk per trade
    
    # Scalping: tight stops/targets (default)
    SCALP_SL_PERCENT: float = 0.01  # 1% stop loss
    SCALP_TP_PERCENT: float = 0.02  # 2% take profit
    
    # Swing: wider stops/targets  
    SWING_SL_PERCENT: float = 0.05  # 5% stop loss
    SWING_TP_PERCENT: float = 0.10  # 10% take profit
    
    # Trade Quality Gate
    MIN_TREND_STRENGTH: float = 0.6  # Minimum trend strength 0-1
    MIN_SETUP_QUALITY: int = 6  # Minimum score to allow trade
    
    # Trade Ranking
    OPPORTUNITY_THRESHOLD: float = 2.0  # Gap to take only best trade
    CORRELATION_FILTER: bool = True  # Avoid correlated pairs
    
    # Performance
    INDICATOR_CACHE_TTL: int = 30
    API_TIMEOUT_SECONDS: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
