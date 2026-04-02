# pip install fastapi uvicorn
# uvicorn service:app --host 0.0.0.0 --port 3010 --reload
# curl http://127.0.0.1:3010/health
# curl -X POST http://127.0.0.1:3010/command

from fastapi import FastAPI, HTTPException
import asyncio
import uuid

app = FastAPI()

# In-memory storage (for demo only)
history_store = {}


async def run_prompt_task(prompt_id: str) -> None:
    try:
        # simulate long-running task
        await asyncio.sleep(30)

        # store result
        history_store[prompt_id] = {
            "status": "completed",
            "result": f"command finished for {prompt_id}"
        }
    except Exception as exc:
        history_store[prompt_id] = {
            "status": "failed",
            "result": str(exc)
        }

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

    # run work in background and return immediately
    asyncio.create_task(run_prompt_task(prompt_id))

    return {
        "prompt_id": prompt_id,
        "message": "command started in background"
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("service:app", host="0.0.0.0", port=3010, reload=True)
