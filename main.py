from fastapi import FastAPI
from api.routes import router
import uvicorn
import os

app = FastAPI(title="AI Trading Bot", version="1.0.0")

app.include_router(router)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
