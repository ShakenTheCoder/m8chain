"""Local POC service: one inference worker, bounded queue, persisted results."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from uuid import uuid4
import shutil
import time
import httpx

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from .models import Analysis, AnalyzeRequest
from .pipeline import AnalysisError, Settings, analyze
from .storage import AnalysisStore, video_id_from_url
from .trends import Trend
from .semantic import SemanticUnavailable

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA = ROOT / ".data"
jobs: dict[str, dict] = {}
lock = Lock()
executor: ThreadPoolExecutor


def store():
    return AnalysisStore(DATA / "organ.sqlite3")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store().initialize()
    # A new lifespan owns a new worker (also permits clean restart in integration tests).
    global executor
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="organ")
    with lock:
        jobs.clear()
    yield
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="n8chain Organ", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    settings = Settings.from_env()
    vision_available = False
    if settings.vision_enabled:
        try:
            response = httpx.get(settings.vision_url.rstrip("/") + "/api/tags", timeout=2)
            response.raise_for_status()
            vision_available = any(m.get("name") == settings.vision_model for m in response.json().get("models", []))
        except (httpx.HTTPError, ValueError, KeyError):
            pass
    return {"ready": bool(settings.apify_token) and bool(shutil.which("ffmpeg")),
            "apify_configured": bool(settings.apify_token), "ffmpeg_installed": bool(shutil.which("ffmpeg")),
            "classifier": settings.laya_model, "languages": ["en", "ro"],
            "vision_enabled": settings.vision_enabled, "vision_available": vision_available,
            "vision_model": settings.vision_model}


@app.get("/schema")
def schema():
    return Analysis.model_json_schema()


def run_job(job_id: str, url: str, settings: Settings):
    started = time.perf_counter()
    def update(stage: str, message: str):
        with lock:
            jobs[job_id].update(stage=stage, message=message)
    try:
        # Another queued link may have resolved to this video since submission.
        saved = store().find(url)
        if saved:
            with lock:
                jobs[job_id].update(stage="complete", message="Loaded saved analysis", result=saved)
            return
        result, raw = analyze(url, settings, update)
        update("saving", "Saving the video and updating trends")
        saved = store().save(result, raw, url, time.perf_counter() - started)
        if saved["id"] != result.id and result.media_evidence.status == "retained":
            shutil.rmtree(settings.evidence_dir / result.id, ignore_errors=True)
        with lock:
            jobs[job_id].update(stage="complete", message="Analysis ready", result=saved)
    except AnalysisError as error:
        update("failed", str(error))
    except Exception:
        update("failed", "Analysis failed. Check your service configuration and try again.")


@app.post("/analyses", status_code=202)
def create_analysis(request: AnalyzeRequest):
    with lock:
        saved = store().find(request.url)
        if saved:
            return JSONResponse({"id": None, "stage": "complete", "cached": True, "result": saved})
        video_id = video_id_from_url(request.url)
        for job in jobs.values():
            if job["stage"] not in {"complete", "failed"} and (job.get("url") == request.url or video_id and job.get("video_id") == video_id):
                return {"id": job["id"], "stage": job["stage"], "cached": False}
        settings = Settings.from_env()
        if not settings.apify_token:
            raise HTTPException(503, "Set APIFY_TOKEN in the repository's .env file, then restart the Python service.")
        if not shutil.which("ffmpeg"):
            raise HTTPException(503, "Install ffmpeg and restart the Python service to enable audio analysis.")
        if sum(j["stage"] not in {"complete", "failed"} for j in jobs.values()) >= 3:
            raise HTTPException(429, "The analysis queue is full. Wait for a running video to finish.")
        if len(jobs) >= 100:
            for key in list(jobs):
                if jobs[key]["stage"] in {"complete", "failed"}:
                    del jobs[key]
                    break
        job_id = str(uuid4())
        jobs[job_id] = {"id": job_id, "stage": "queued", "message": "Waiting for the analysis worker", "result": None,
                        "url": request.url, "video_id": video_id}
    executor.submit(run_job, job_id, request.url, settings)
    return {"id": job_id, "stage": "queued", "cached": False}


@app.get("/analyses")
def list_analyses(limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    return store().list(limit, offset)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Analysis job not found. It may have expired or the service restarted.")
        return dict(job)


@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    result = store().get(analysis_id)
    if result is None:
        raise HTTPException(404, "Analysis not found.")
    return JSONResponse(result)


@app.get("/trends/schema")
def trend_schema():
    return Trend.model_json_schema()


@app.get("/trends")
def list_trends():
    try:
        return {key: value for key, value in store().trend_snapshot().items() if key != "graph"}
    except SemanticUnavailable as error:
        raise HTTPException(503, str(error)) from None


@app.get("/graph")
def video_graph():
    try:
        snapshot = store().trend_snapshot()
    except SemanticUnavailable as error:
        raise HTTPException(503, str(error)) from None
    return {**snapshot["graph"], "revision": snapshot["revision"], "updated_at": snapshot["updated_at"]}
