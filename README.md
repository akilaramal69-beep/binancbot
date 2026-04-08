# 🚀 AI Trading Bot (Binance Independent Scanner)

A powerful, Dockerized AI trading bot that proactively scans the Binance market and executes trades based on a **Triple-Verification** strategy. No TradingView required!

## ✨ Features
- **Independent Market Scanner**: Proactively watches BTC, ETH, SOL, and BNB.
- **Binance Optimization**: Async execution with support for $10 minimum budget.
- **Demo Mode**: Built-in testnet support and simulated execution reports.
- **Telegram Alerts**: Real-time notifications for every analysis and trade step.
- **Auto-Koyeb**: Ready for cloud deployment.

## 🛠 Setup & Installation

### 1. Environment Variables
Create a `.env` file based on `.env.example`:
```env
EXCHANGE_ID=binance
EXCHANGE_API_KEY=your_binance_key
EXCHANGE_SECRET=your_binance_secret
USE_TESTNET=true # Set to false for live trading

WATCH_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT
SCAN_INTERVAL_MINUTES=15

OPENAI_API_KEY=your_openai_key
ALPHA_VANTAGE_API_KEY=your_av_key
GROQ_API_KEY=your_groq_key
GROQ_MODEL=gpt-oss-120b

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ENABLE_TELEGRAM=true
```

### 2. Local Run
```bash
pip install -r requirements.txt
python main.py
```

### 3. Deployment (Koyeb)
- **Service Type**: Web Service.
- **Port**: 8000.
- **Docker**: Automatically uses the provided `Dockerfile`.

## 📈 Independent Scanner Setup
The bot will automatically scan the coins defined in `WATCH_SYMBOLS` every `SCAN_INTERVAL_MINUTES`. No manual setup is needed on TradingView.

## 🧪 Testing (Paper Trading)
To test with fake money:
1. Go to [Binance Spot Testnet](https://testnet.binance.vision/).
2. Get Testnet API keys and set `USE_TESTNET=true`.

---
**⚠️ Budget Note**: This bot is optimized for small accounts ($10 starting budget). It automatically adjusts position sizes to meet Binance's minimum order requirements.

**Disclaimer**: Use this bot at your own risk. Trading involves significant financial danger.
