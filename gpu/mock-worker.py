import os
from aiohttp import web
from vastai import BenchmarkConfig, HandlerConfig, LogActionConfig, Worker, WorkerConfig

# Keep defaults compatible with Vast runtime and local execution.
os.environ.setdefault("UNSECURED", "true")
WORKER_PORT = int(os.environ.get("WORKER_PORT", "3000"))
os.environ.setdefault("WORKER_PORT", str(WORKER_PORT))
os.environ.setdefault("CONTAINER_ID", "0")
os.environ.setdefault("REPORT_ADDR", "https://run.vast.ai")
os.environ.setdefault("PUBLIC_IPADDR", "0.0.0.0")
os.environ.setdefault("USE_SSL", "false")
os.environ.setdefault(f"VAST_TCP_PORT_{WORKER_PORT}", str(WORKER_PORT))

MODEL_SERVER_URL = os.environ.get("MODEL_SERVER_URL", "http://0.0.0.0")
MODEL_SERVER_PORT = int(os.environ.get("MODEL_SERVER_PORT", "3010"))
MODEL_LOG_FILE = os.environ.get("MODEL_LOG_FILE", "/var/log/portal/model.log")
MODEL_HEALTHCHECK_ENDPOINT = os.environ.get("MODEL_HEALTHCHECK_ENDPOINT", "/health")

# Vast requires benchmark data on at least one handler.
BENCHMARK_DATASET = [{"input": {"prompt": {}}}]


async def _always_success(**params):
    return {
        "success": True,
        "status": "completed",
        "message": "Mock worker accepted request",
        "input": params,
        "status_code": 200,
    }


async def _response_generator(client_request: web.Request, model_response):
    # Keep HTTP response status fixed to success for every request path.
    _ = (client_request, model_response)
    return web.json_response(
        {
            "success": True,
            "status": "completed",
            "message": "Mock worker response",
        },
        status=200,
    )


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
            remote_function=_always_success,
            response_generator=_response_generator,
        ),
        HandlerConfig(
            route="/prompt",
            allow_parallel_requests=True,
            max_queue_time=10.0,
            benchmark_config=BenchmarkConfig(dataset=BENCHMARK_DATASET),
            remote_function=_always_success,
            response_generator=_response_generator,
        ),
    ],
    log_action_config=LogActionConfig(
        on_load=["Mock worker loaded"],
        on_error=["Mock worker error"],
        on_info=["Mock worker info"],
    ),
)


Worker(worker_config).run()
