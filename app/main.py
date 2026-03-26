from fastapi import FastAPI


app = FastAPI(
    title="Grid Interconnection & Energy Siting Copilot",
    version="0.1.0",
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}

