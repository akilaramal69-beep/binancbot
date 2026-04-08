# 🚀 AI Trading Bot (Binance + TradingView + Telegram)

A powerful, Dockerized AI trading bot that integrates TradingView webhooks, Binance API, and Telegram notifications. It uses a **Triple-Verification** strategy:
1. **Binance**: Real-time Fibonacci support/resistance levels.
2. **Alpha Vantage**: News sentiment and Technical trend (EMA) verification.
3. **Deep AI**: Sentiment analysis of market news using LLMs (OpenAI/Groq).

## ✨ Features
- **Binance Optimization**: Async execution with support for $10 minimum budget.
- **Demo Mode**: Built-in simulation mode (`"is_demo": true`) and Binance Testnet support.
- **Telegram Alerts**: Real-time notifications for every analysis and trade step.
- **Auto-Koyeb**: One-click Docker deployment.

## 🛠 Setup & Installation

### 1. Environment Variables
Create a `.env` file based on `.env.example`:
```env
EXCHANGE_API_KEY=your_binance_key
EXCHANGE_SECRET=your_binance_secret
USE_TESTNET=true # Set to false for live trading

OPENAI_API_KEY=your_openai_key
ALPHA_VANTAGE_API_KEY=your_av_key

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ENABLE_TELEGRAM=true

WEBHOOK_PASSPHRASE=your_secret_password
```

### 2. Local Run
```bash
pip install -r requirements.txt
python main.py
```

### 3. Deployment (Koyeb)
- **Service Type**: Web Service (Not Worker).
- **Port**: 8000.
- **Docker**: Automatically uses the provided `Dockerfile`.

## 📈 TradingView Configuration
Set a Webhook alert on TradingView:
- **URL**: `https://your-app-url.koyeb.app/webhook`
- **JSON Body**:
```json
{
  "passphrase": "your_secret_password",
  "symbol": "BTC/USDT",
  "side": "buy",
  "price": {{close}},
  "is_demo": true
}
```

## 🧪 Testing (Paper Trading)
To test with fake money:
1. Go to [Binance Spot Testnet](https://testnet.binance.vision/).
2. Get Testnet API keys and set `USE_TESTNET=true`.
3. Use `"is_demo": true` in TradingView for "simulation-only" mode (no trading at all).

---
**Disclaimer**: Use this bot at your own risk. Trading involves significant financial danger.
