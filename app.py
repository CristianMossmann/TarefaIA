import asyncio
import logging

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from services.capture_store import CaptureStore
from services.config import settings
from services.event_repository import EventRepository
from services.monitoring_agent import build_agent_messages, build_agent_status
from services.ollama_client import OllamaClient, OllamaUnavailableError
from services.schemas import ChatRequest, ChatResponse
from services.scraping import ScrapingService
from services.video_monitor import VideoMonitor


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger(__name__)


app = FastAPI(title=settings.app_title)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
templates = Jinja2Templates(directory=str(settings.templates_dir))

event_repository = EventRepository(settings.db_path)
capture_store = CaptureStore(settings.save_dir)
ollama_client = OllamaClient(
    base_chat_url=settings.ollama_url,
    model=settings.ollama_model,
    timeout_seconds=settings.ollama_timeout,
    keep_alive=settings.ollama_keep_alive,
)
scraping_service = ScrapingService(
    weather_location=settings.scraping_weather_location,
    weather_ttl_seconds=settings.scraping_weather_ttl,
    commodities_ttl_seconds=settings.scraping_commodities_ttl,
    request_timeout=settings.scraping_request_timeout,
    max_requests_per_minute=settings.scraping_max_rpm,
)
video_monitor = VideoMonitor(
    camera_source=settings.camera_source,
    model_path=settings.model_path,
    confidence_threshold=settings.confidence_threshold,
    target_classes=settings.target_classes,
    min_consecutive_frames=settings.min_consecutive_frames,
    alert_cooldown_seconds=settings.alert_cooldown_seconds,
    reconnect_seconds=settings.camera_reconnect_seconds,
    save_dir=settings.save_dir,
    event_repository=event_repository,
)


@app.on_event("startup")
def startup_event() -> None:
    event_repository.init_db()
    video_monitor.start()
    ollama_client.warmup()


@app.on_event("shutdown")
def shutdown_event() -> None:
    video_monitor.stop()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    events = event_repository.list_events(20)
    captures = capture_store.list_recent(12)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "events": events,
            "captures": captures,
            "agent_name": "Agente AgroVision",
        },
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_title}


@app.get("/events")
def get_events(limit: int = Query(default=50, ge=1, le=200)):
    return JSONResponse(content=event_repository.list_events(limit))


@app.get("/camera/status")
def camera_status() -> dict:
    return video_monitor.status()


@app.get("/frame")
def get_frame():
    frame_bytes = video_monitor.get_last_frame_jpeg()
    if frame_bytes is None:
        return JSONResponse(
            content={"message": "Ainda sem frame disponivel."},
            status_code=503,
        )
    return Response(content=frame_bytes, media_type="image/jpeg")


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(
        video_monitor.frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/agent/status")
def agent_status() -> dict:
    events = event_repository.list_events(settings.agent_event_limit)
    return build_agent_status(events)


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    events = event_repository.list_events(settings.agent_event_limit)
    history = [msg.model_dump() for msg in payload.history]
    weather_snapshot = scraping_service.weather_snapshot_for_agent()
    messages = build_agent_messages(payload.question, history, events, weather_snapshot)

    try:
        answer = await asyncio.to_thread(ollama_client.chat, messages)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ChatResponse(answer=answer, model=settings.ollama_model)


@app.get("/scraping/weather")
async def scraping_weather():
    result = await asyncio.to_thread(scraping_service.get_weather)
    if result["status"] != "ok":
        return JSONResponse(content=result, status_code=503)
    return result


@app.get("/scraping/commodities")
async def scraping_commodities():
    result = await asyncio.to_thread(scraping_service.get_commodities)
    if result["status"] != "ok":
        return JSONResponse(content=result, status_code=503)
    return result
