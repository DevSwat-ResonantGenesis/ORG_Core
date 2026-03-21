from fastapi import FastAPI

from .routers import router

app = FastAPI(
    title="LLM Service",
    description="Chat completion, agent reasoning, and tool-calling system",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health")
async def root_health() -> dict:
    return {"service": "llm", "status": "ok"}
