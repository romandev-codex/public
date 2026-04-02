import asyncio
import json
import os
from urllib.parse import urlencode
from aiohttp import ClientResponse, ClientSession, ClientTimeout, web
from vastai import Worker, WorkerConfig, HandlerConfig, LogActionConfig, BenchmarkConfig
from vastai.serverless.server.lib import backend as vast_backend
from contextvars import ContextVar

# os.environ.setdefault("UNSECURED", "true")
os.environ.setdefault("UNSECURED", "false")

# python worker.py
WORKER_PORT = int(os.environ.get("WORKER_PORT", "3000"))

# Running locally (outside Vast runtime) may miss required metrics env vars.
os.environ.setdefault("WORKER_PORT", str(WORKER_PORT))
os.environ.setdefault("CONTAINER_ID", "0")
os.environ.setdefault("REPORT_ADDR", "https://run.vast.ai")
os.environ.setdefault("PUBLIC_IPADDR", "0.0.0.0")
os.environ.setdefault("USE_SSL", "false")
os.environ.setdefault(f"VAST_TCP_PORT_{os.environ['WORKER_PORT']}", os.environ["WORKER_PORT"])

# ComyUI model configuration
MODEL_SERVER_URL           = os.environ.get("MODEL_SERVER_URL", "http://0.0.0.0")
MODEL_SERVER_PORT          = int(os.environ.get("MODEL_SERVER_PORT", "3010"))
MODEL_LOG_FILE             = os.environ.get("MODEL_LOG_FILE", "/var/log/portal/model.log")
MODEL_HEALTHCHECK_ENDPOINT = os.environ.get("MODEL_HEALTHCHECK_ENDPOINT", "/health")

# Vast worker requires at least one handler to expose benchmark config.
BENCHMARK_DATASET = [
    {
        "input": {
            "prompt": {},
        }
    }
]

_CURRENT_QUERY_PARAMS: ContextVar[dict | None] = ContextVar("current_query_params", default=None)
_BACKGROUND_PROMPT_WORKER_TASK: asyncio.Task | None = None
_BACKGROUND_PROMPT_BUSY = False
_BACKGROUND_PROMPT_STATE_LOCK = asyncio.Lock()
_COMFY_POLL_INTERVAL_SECONDS = 1.0
_COMFY_PROMPT_TIMEOUT_SECONDS = 1800.0


def _extract_prompt_id(response_body: bytes) -> str | None:
    try:
        parsed = json.loads(response_body)
    except Exception:
        return None

    if isinstance(parsed, dict):
        prompt_id = parsed.get("prompt_id")
        if isinstance(prompt_id, str) and prompt_id:
            return prompt_id
    return None


async def _wait_for_prompt_completion(
    session: ClientSession,
    prompt_id: str,
    query_params: dict,
) -> None:
    history_url = f"{MODEL_SERVER_URL}:{MODEL_SERVER_PORT}/history/{prompt_id}"
    terminal_states = {"success", "error", "failed", "interrupted", "cancelled"}
    deadline = asyncio.get_running_loop().time() + _COMFY_PROMPT_TIMEOUT_SECONDS

    while True:
        if asyncio.get_running_loop().time() >= deadline:
            print(f"Background prompt timed out after {_COMFY_PROMPT_TIMEOUT_SECONDS}s for prompt_id={prompt_id}")
            return

        try:
            async with session.get(history_url, params=query_params or None) as response:
                if response.status != 200:
                    await asyncio.sleep(_COMFY_POLL_INTERVAL_SECONDS)
                    continue

                history_payload = await response.json(content_type=None)
                if not isinstance(history_payload, dict):
                    await asyncio.sleep(_COMFY_POLL_INTERVAL_SECONDS)
                    continue

                prompt_entry = history_payload.get(prompt_id)
                if not isinstance(prompt_entry, dict):
                    await asyncio.sleep(_COMFY_POLL_INTERVAL_SECONDS)
                    continue

                status = prompt_entry.get("status")
                if not isinstance(status, dict):
                    await asyncio.sleep(_COMFY_POLL_INTERVAL_SECONDS)
                    continue

                if status.get("completed") is True:
                    return

                status_str = status.get("status_str")
                if isinstance(status_str, str) and status_str.lower() in terminal_states:
                    return
        except Exception:
            # Best effort polling; keep trying until ComfyUI reports a terminal state.
            pass

        await asyncio.sleep(_COMFY_POLL_INTERVAL_SECONDS)


async def _track_prompt_completion_in_background(prompt_id: str, query_params: dict) -> None:
    timeout = ClientTimeout(total=None)
    try:
        async with ClientSession(timeout=timeout) as session:
            await _wait_for_prompt_completion(
                session=session,
                prompt_id=prompt_id,
                query_params=query_params,
            )
    except Exception as ex:
        print(f"Background prompt execution failed: {ex}")
    finally:
        global _BACKGROUND_PROMPT_BUSY
        async with _BACKGROUND_PROMPT_STATE_LOCK:
            _BACKGROUND_PROMPT_BUSY = False


async def _dispatch_prompt_in_background(**params):
    global _BACKGROUND_PROMPT_WORKER_TASK
    global _BACKGROUND_PROMPT_BUSY
    query_params = _CURRENT_QUERY_PARAMS.get() or {}
    model_prompt_url = f"{MODEL_SERVER_URL}:{MODEL_SERVER_PORT}/prompt"

    async with _BACKGROUND_PROMPT_STATE_LOCK:
        if _BACKGROUND_PROMPT_BUSY:
            return {
                "status": "busy",
                "message": "Worker already has an active run",
                "status_code": 429,
            }

        _BACKGROUND_PROMPT_BUSY = True

    timeout = ClientTimeout(total=None)
    try:
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                url=model_prompt_url,
                json=params,
                params=query_params or None,
            ) as model_response:
                response_body = await model_response.read()
                response_status = model_response.status
    except Exception as ex:
        async with _BACKGROUND_PROMPT_STATE_LOCK:
            _BACKGROUND_PROMPT_BUSY = False
        return {
            "status": "error",
            "message": f"Failed to dispatch prompt to ComfyUI: {ex}",
            "status_code": 502,
        }

    prompt_id = _extract_prompt_id(response_body)
    if not prompt_id:
        async with _BACKGROUND_PROMPT_STATE_LOCK:
            _BACKGROUND_PROMPT_BUSY = False
        return {
            "status": "error",
            "message": "ComfyUI response missing prompt_id",
            "comfyui_status": response_status,
            "comfyui_response": response_body.decode("utf-8", errors="replace"),
            "status_code": 502,
        }

    _BACKGROUND_PROMPT_WORKER_TASK = asyncio.create_task(
        _track_prompt_completion_in_background(prompt_id, query_params)
    )

    try:
        comfyui_response = json.loads(response_body)
    except Exception:
        comfyui_response = response_body.decode("utf-8", errors="replace")

    history_url = f"{MODEL_SERVER_URL}:{MODEL_SERVER_PORT}/history/{prompt_id}"
    status_url = history_url
    if query_params:
        status_url = f"{history_url}?{urlencode(query_params)}"

    return {
        "prompt_id": prompt_id,
        "status_url": status_url,
        "server_url": f"{MODEL_SERVER_URL}:{MODEL_SERVER_PORT}",
        "comfyui_status": response_status,
        "comfyui_response": comfyui_response,
        "status_code": 202,
    }


def _patch_vast_backend_query_forwarding() -> None:
    # Forward incoming worker query params (e.g. ?token=...) to model server POST calls.
    if getattr(vast_backend.Backend, "_token_query_forwarding_patched", False):
        return

    original_create_handler = vast_backend.Backend.create_handler
    original_call_api = vast_backend.Backend._Backend__call_api

    def create_handler_with_query_context(self, handler):
        handler_fn = original_create_handler(self, handler)

        async def wrapped_handler(request: web.Request):
            query_params = dict(request.query)
            token = _CURRENT_QUERY_PARAMS.set(query_params)
            try:
                return await handler_fn(request)
            finally:
                _CURRENT_QUERY_PARAMS.reset(token)

        return wrapped_handler

    async def call_api_with_query_forwarding(self, handler, payload):
        query_params = _CURRENT_QUERY_PARAMS.get()
        if query_params:
            return await self.session.post(
                url=handler.endpoint,
                json=payload.generate_payload_json(),
                params=query_params,
            )
        return await original_call_api(self, handler, payload)

    vast_backend.Backend.create_handler = create_handler_with_query_context
    vast_backend.Backend._Backend__call_api = call_api_with_query_forwarding
    vast_backend.Backend._token_query_forwarding_patched = True


_patch_vast_backend_query_forwarding()

async def _prompt_response_generator(
    client_request: web.Request,
    model_response: ClientResponse,
) -> web.Response:
    body = await model_response.read()

    # Remote dispatch responses are wrapped as {"result": ...}.
    # If result contains status_code, map it to the HTTP response status.
    try:
        parsed = json.loads(body)
        result = parsed.get("result") if isinstance(parsed, dict) else None
        if isinstance(result, dict) and "status_code" in result:
            response_status = int(result["status_code"])
            response_body = {k: v for k, v in result.items() if k != "status_code"}
            return web.json_response(response_body, status=response_status)
    except Exception:
        pass

    return web.Response(
        body=body,
        status=model_response.status,
        content_type=model_response.content_type or "application/json",
    )

def _constant_workload(payload: dict) -> float:
    return 1.0

worker_config = WorkerConfig(
    model_server_url=MODEL_SERVER_URL,
    model_server_port=MODEL_SERVER_PORT,
    model_log_file=MODEL_LOG_FILE,
    model_healthcheck_url=MODEL_HEALTHCHECK_ENDPOINT,
    handlers=[
        HandlerConfig(
            route="/health",
            allow_parallel_requests=True,
            max_queue_time=10.0,
        ),
        HandlerConfig(
            route="/prompt",
            allow_parallel_requests=False,
            max_queue_time=60.0,
            benchmark_config=BenchmarkConfig(
                dataset=BENCHMARK_DATASET,
            ),
            response_generator=_prompt_response_generator,
            remote_function=_dispatch_prompt_in_background,
            workload_calculator=_constant_workload,
        ),
    ],
    log_action_config=LogActionConfig(
        on_load=[
            "To see the GUI go to:",
            "Starting server",
        ],
        on_error=[
            "Traceback (most recent call last):",
            "RuntimeError",
            "ModuleNotFoundError",
        ],
        on_info=[],
    ),
)

Worker(worker_config).run()
