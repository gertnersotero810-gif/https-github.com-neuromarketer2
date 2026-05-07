from fastapi import FastAPI

app = FastAPI(title="НейроМаркетолог API", version="0.1.0")


@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
