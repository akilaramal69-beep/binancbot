from fastapi import FastAPI
from api.routes import router
from services.scanner import MarketScanner
import uvicorn
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from services.telegram import TelegramService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start scanner on startup
    scanner = MarketScanner()
    asyncio.create_task(scanner.run_forever())
    
    # Start Telegram interactive bot
    asyncio.create_task(TelegramService.start_interactive_bot())
    
    yield
    # Shutdown logic if needed

app = FastAPI(title="AI Trading Bot", version="2.0.0", lifespan=lifespan)

app.include_router(router)

# Mount Static Files for WebUI
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
