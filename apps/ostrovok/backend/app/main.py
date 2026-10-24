"""Single-origin demo API and built frontend entry point."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from app.agent.model_gateway import ModelGateway
from app.domain.models import (
    InputMessage,
    ChangeMessage,
    Selection,
    VersionRequest,
    Confirmation,
)
from app.service import TripService
from app.storage import Store


class CreateInput(InputMessage):
    model_config = ConfigDict(extra="forbid", strict=True)


class ChangeInput(ChangeMessage):
    model_config = ConfigDict(extra="forbid", strict=True)


class SelectInput(Selection):
    model_config = ConfigDict(extra="forbid", strict=True)


class VersionInput(VersionRequest):
    model_config = ConfigDict(extra="forbid", strict=True)


class ConfirmInput(Confirmation):
    model_config = ConfigDict(extra="forbid", strict=True)


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preferences: dict


class ServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: str = Field(max_length=64)
    message: str = Field(default="", max_length=1000)


def create_app(db_path=None, clock=None, gateway=None):
    app = FastAPI(title="О!Собрано — demo travel agent", version="1.0.0")
    store = Store(db_path or os.environ.get("DB_PATH", "./var/ostrovok.sqlite"))
    service = TripService(
        store, clock or (lambda: datetime.now(timezone.utc)), gateway or ModelGateway()
    )
    app.state.store = store
    app.state.service = service

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        first = error.errors()[0]
        field = ".".join(str(x) for x in first["loc"] if x != "body")
        return JSONResponse(
            status_code=422, content={"detail": f"{field}: {first['msg']}"}
        )

    @app.middleware("http")
    async def sessions(request, call_next):
        fresh = False
        if request.url.path.startswith("/api/"):
            token, fresh = store.session(
                request.cookies.get("ostrovok_session"), service.now()
            )
            request.state.session_id = token
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            if fresh:
                response.set_cookie(
                    "ostrovok_session",
                    request.state.session_id,
                    httponly=True,
                    samesite="lax",
                    secure=request.url.scheme == "https"
                    or os.environ.get("COOKIE_SECURE") == "1",
                    max_age=30 * 24 * 60 * 60,
                    path="/",
                )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        if not store.healthy():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "storage": "sqlite",
                    "detail": "Хранилище SQLite недоступно.",
                },
            )
        return {"status": "ok", "mode": "demo", "storage": "sqlite"}

    @app.get("/api/capabilities")
    def capabilities():
        return service.capabilities()

    @app.get("/api/trips")
    def history(request: Request):
        return {"trips": store.history(request.state.session_id)}

    @app.post("/api/trips")
    async def create(body: CreateInput, request: Request):
        return await service.create(request.state.session_id, body.message, body.patch)

    @app.get("/api/trips/{trip_id}")
    def trip(trip_id: str, request: Request):
        return store.get(trip_id, request.state.session_id)

    @app.post("/api/trips/{trip_id}/messages")
    async def change(trip_id: str, body: ChangeInput, request: Request):
        return await service.change(
            trip_id,
            request.state.session_id,
            body.expected_version,
            body.message,
            body.patch,
        )

    @app.post("/api/trips/{trip_id}/selection")
    def selection(trip_id: str, body: SelectInput, request: Request):
        return service.select(
            trip_id, request.state.session_id, body.expected_version, body.plan_id
        )

    @app.post("/api/trips/{trip_id}/quote")
    def quote(trip_id: str, body: VersionInput, request: Request):
        return service.quote(trip_id, request.state.session_id, body.expected_version)

    @app.post("/api/trips/{trip_id}/demo-orders")
    def purchase(trip_id: str, body: ConfirmInput, request: Request):
        return service.purchase(
            trip_id,
            request.state.session_id,
            body.model_dump(),
            request.headers.get("Idempotency-Key"),
        )

    @app.get("/api/demo-orders/{order_id}")
    def order(order_id: str, request: Request):
        return store.order(order_id, request.state.session_id)

    @app.get("/api/trips/{trip_id}/events")
    def events(trip_id: str, request: Request):
        store.get(trip_id, request.state.session_id)
        try:
            after = int(request.headers.get("Last-Event-ID", "0"))
        except ValueError:
            raise HTTPException(422, "Last-Event-ID должен быть целым числом.")
        rows = store.events(trip_id, request.state.session_id, max(0, after))
        content = "".join(
            f"id: {event_id}\nevent: {body['type']}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"
            for event_id, body in rows
        )
        return Response(
            content or ": no new committed events\n\n",
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/preferences")
    def preferences(request: Request):
        return {"preferences": service.preferences(request.state.session_id)}

    @app.put("/api/preferences")
    def save_preferences(body: PreferenceInput, request: Request):
        return {
            "preferences": service.preferences(
                request.state.session_id, body.preferences
            )
        }

    @app.delete("/api/preferences")
    def delete_preferences(request: Request):
        return {"preferences": service.preferences(request.state.session_id, {})}

    @app.post("/api/trips/{trip_id}/service-requests")
    def service_request(trip_id: str, body: ServiceInput, request: Request):
        return service.service_request(
            trip_id, request.state.session_id, body.kind, body.message
        )

    dist = Path(__file__).resolve().parents[2] / "frontend/dist"
    app.mount(
        "/assets",
        StaticFiles(directory=dist / "assets", check_dir=False),
        name="assets",
    )

    @app.get("/{path:path}")
    def frontend(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "API endpoint не найден.")
        candidate = (dist / path).resolve()
        if candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Frontend ещё не собран. Выполните npm run build в apps/ostrovok/frontend."
            },
        )

    return app


app = create_app()
