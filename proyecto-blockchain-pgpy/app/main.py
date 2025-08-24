from fastapi import FastAPI
from api.routes import router

app = FastAPI(title="Consensus API (PGPy)")
app.include_router(router)
