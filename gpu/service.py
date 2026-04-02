# pip install fastapi uvicorn
# uvicorn service:app --host 0.0.0.0 --port 3010 --reload
# curl http://127.0.0.1:3010/health
# curl -X POST http://127.0.0.1:3010/command

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import json
import uuid
from pathlib import Path

app = FastAPI()

# Persist history on disk so IDs survive reload/restart.
HISTORY_FILE = Path(__file__).with_name("history_store.json")
history_store = {}


def load_history_store() -> dict:
    if not HISTORY_FILE.exists():
        return {}
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_history_store() -> None:
    with HISTORY_FILE.open("w", encoding="utf-8") as file_obj:
        json.dump(history_store, file_obj, ensure_ascii=True, indent=2)


@app.on_event("startup")
async def startup_event() -> None:
    global history_store
    history_store = load_history_store()


async def run_prompt_task(prompt_id: str) -> None:
    try:
        # simulate long-running task
        await asyncio.sleep(10)

        # store result
        history_store[prompt_id] = {
            "status": "completed",
            "result": f"command finished for {prompt_id}"
        }
        save_history_store()
    except Exception as exc:
        history_store[prompt_id] = {
            "status": "failed",
            "result": str(exc)
        }
        save_history_store()

# 1. Status endpoint
@app.get("/health")
async def status():
    return {"status": "ok"}

# 2. Command endpoint with 10-second delay
@app.post("/prompt")
async def prompt():
    prompt_id = str(uuid.uuid4())

    # mark as pending
    history_store[prompt_id] = {"status": "pending", "result": None}
    save_history_store()

    # run work in background and return immediately
    asyncio.create_task(run_prompt_task(prompt_id))

    return {
        "prompt_id": prompt_id,
        "message": "command started in background"
    }

# 3. History endpoint
@app.get("/history/{promptid}")
async def get_history(promptid: str):
    normalized_prompt_id = promptid.strip()
    if normalized_prompt_id not in history_store:
        raise HTTPException(status_code=404, detail="Prompt ID not found")

    payload = {
        "prompt_id": normalized_prompt_id,
        **history_store[normalized_prompt_id]
    }

    status = payload.get("status")
    if status == "completed":
        return payload
    if status == "pending":
        return JSONResponse(status_code=202, content=payload)
    if status == "failed":
        return JSONResponse(status_code=500, content=payload)

    return JSONResponse(status_code=202, content=payload)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=3010, reload=True)
