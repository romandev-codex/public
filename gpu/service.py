# pip install fastapi uvicorn
# uvicorn service:app --reload
# curl http://127.0.0.1:8000/health
# curl -X POST http://127.0.0.1:8000/command

from fastapi import FastAPI, HTTPException
import asyncio
import uuid

app = FastAPI()

# In-memory storage (for demo only)
history_store = {}

# 1. Status endpoint
@app.get("/health")
async def status():
    return {"status": "ok"}

# 2. Command endpoint with 30-second delay
@app.post("/prompt")
async def prompt():
    prompt_id = str(uuid.uuid4())

    # mark as pending
    history_store[prompt_id] = {"status": "pending", "result": None}

    # simulate long-running task
    await asyncio.sleep(30)

    # store result
    history_store[prompt_id] = {
        "status": "completed",
        "result": f"command finished for {prompt_id}"
    }

    return {
        "prompt_id": prompt_id,
        "message": "command executed after 30 seconds"
    }

# 3. History endpoint
@app.get("/history/{promptid}")
async def get_history(promptid: str):
    if promptid not in history_store:
        raise HTTPException(status_code=404, detail="Prompt ID not found")

    return {
        "prompt_id": promptid,
        **history_store[promptid]
    }
