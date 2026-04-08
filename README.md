# 🚀 AI Trading Sniper (Groq 120B)

A fully autonomous, proactive crypto trading bot built for Binance. It continuously scans the market, executes triple-verification technical and fundamental analysis, and manages trades with "Pro-Trader" risk management—all optimized for small budgets.

## 🌟 Key Features

* **Proactive Market Scanner**: Runs continuously in the background (configurable interval) without manual prompts.
* **Institutional Scoring Engine (10-Point System)**:
    * **Structure & Trend**: Validates Exponential Moving Averages (EMA gaps) and dynamic Break of Structure (BOS).
    * **Volume & Volatility**: Calculates Average True Range (ATR) and rolling Volume Spikes to execute strictly on market expansion. 
    * **Fundamental Intelligence**: Measures Absolute Sentiment & Acceleration (+3 points for rapid hype conviction) using Groq AI (`gpt-oss-120b`).
    * **Fakeout Filters**: Employs "Darth Maul Wick" rejection, rigid Closing Body ratios, and Distance-from-Range (FOMO) filters to ensure mathematical precision before entering.
* **Pro-Trader Risk Management**:
    * **Multi-Step Exit**: Automatically moves Stop-Loss to True Breakeven (Entry + Binance slippage fee) at 50% target. Scales out 50% of the position at 90% target.
    * **ATR-Based Scaling**: Automatically scales Stop-Loss (`-1.5*ATR`) and Take-Profit (`+3.0*ATR`) to adapt dynamically to active asset volatility.
    * **Micro-Budget Compatible**: Safely satisfies Binance `LOT_SIZE` and `MIN_NOTIONAL` requirements on tests as low as $11.50.
* **Dynamic Modularity**:
    * **Fast Trade Mode**: Dedicated toggle in `config.py` that widens structural tolerances and lowers required AI confidence floors to support high-frequency scalping.
* **Interactive Dashboards**:
    * **Modern WebUI**: A premium dark-mode web dashboard showcasing a rolling **AI Intelligence Feed**, tracking every score metric in real-time.
    * **Telegram GUI**: Full operational oversight right from your phone via `/status` and `/holdings`.

---

## ⚙️ Configuration & Deployment

### 1. Environment Setup
Create a `.env` file containing your API keys (or add them to your Koyeb Environment Variables):
```env
EXCHANGE_API_KEY=your_binance_api_key
EXCHANGE_SECRET=your_binance_secret
USE_TESTNET=true # Set to false for real-money Mainnet

GROQ_API_KEY=your_groq_key
GROQ_MODEL=llama-3.1-70b-versatile # Recommended fast model

ALPHA_VANTAGE_API_KEY=your_av_key

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
ENABLE_TELEGRAM=true

WATCH_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT
SCAN_INTERVAL_MINUTES=15
```

### 2. Live Dependencies
Ensure your `requirements.txt` is installed:
```bash
pip install -r requirements.txt
```

### 3. Run the Bot
The bot runs via FastAPI/Uvicorn, serving the web dashboard while executing the market scanner in the background.
```bash
python main.py
```

---

## 📈 Dashboard Features

Once running, access your bot via the local or deployed URL (e.g., `http://localhost:8000/`).

* **Live Analytics**: 30-second interval updates.
* **Total Lifetime Scans**: Count of all market assessments independent of server reboots.
* **Rolling Intelligence**: Watch exactly what price, Fib level, and Sentiment score the AI is processing in real-time.

---
*Built with ❤️ for precision algorithmic trading.*
