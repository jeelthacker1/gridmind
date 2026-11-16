import os, json, time, hashlib, secrets, asyncio, io, logging
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal
import pandas as pd
from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    File,
    Form,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from .db import Session, User, LoginSession, Factory, Dataset, Run, Playback, Audit
from .security import current, editor, admin, verify, hash_password, audit
from .energy import Config
from .data import ingest
from .jobs import enqueue

logging.basicConfig(
    level=logging.INFO, format='{"level":"%(levelname)s","message":"%(message)s"}'
)


@asynccontextmanager
async def lifespan(app):
    yield


app = FastAPI(title="GRIDMIND", version="1.0.0", lifespan=lifespan)
attempts = defaultdict(deque)


@app.middleware("http")
async def protection(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = os.getenv("APP_ORIGIN", "http://localhost:3000").split(",")
        if origin and origin not in allowed:
            return Response("Origin rejected", 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return Response("Cross-site request rejected", 403)
    if request.url.path == "/api/login":
        key = request.client.host if request.client else "unknown"
        now = time.time()
        if os.getenv("REDIS_URL"):
            from redis import Redis

            try:
                r = Redis.from_url(os.environ["REDIS_URL"])
                bucket = f"login:{key}:{int(now//60)}"
                count = r.incr(bucket)
                r.expire(bucket, 120)
                if count > 20:
                    return Response("Too many login attempts", 429)
            except Exception:
                return Response("Authentication temporarily unavailable", 503)
        else:
            q = attempts[key]
            while q and q[0] < now - 60:
                q.popleft()
            if len(q) >= 20:
                return Response("Too many login attempts", 429)
            q.append(now)
    result = await call_next(request)
    result.headers["X-Content-Type-Options"] = "nosniff"
    result.headers["X-Frame-Options"] = "DENY"
    result.headers["Cache-Control"] = "no-store"
    return result


class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


@app.get("/api/health")
def health():
    from sqlalchemy import text

    with Session() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/login")
def login(body: Login, response: Response):
    with Session() as db:
        user = db.scalar(select(User).where(User.email == body.email))
        if not user or not verify(body.password, user.password):
            audit(None, "login_failed")
            raise HTTPException(401, "Invalid credentials")
        token = secrets.token_urlsafe(32)
        db.add(
            LoginSession(
                token=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user.id,
                expires=time.time() + 28800,
            )
        )
        db.commit()
        response.set_cookie(
            "gridmind",
            token,
            httponly=True,
            samesite="strict",
            secure=os.getenv("COOKIE_SECURE", "false") == "true",
            max_age=28800,
        )
        audit(user.id, "login")
        return {"email": user.email, "role": user.role}


@app.post("/api/logout")
def logout(request: Request, response: Response, user=Depends(current)):
    with Session() as db:
        item = db.get(
            LoginSession,
            hashlib.sha256(request.cookies.get("gridmind", "").encode()).hexdigest(),
        )
        if item:
            db.delete(item)
            db.commit()
    response.delete_cookie("gridmind")
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current)):
    return {"email": user.email, "role": user.role}


class NewUser(Login):
    role: Literal["admin", "analyst", "viewer"] = "viewer"


@app.post("/api/users")
def new_user(body: NewUser, user=Depends(admin)):
    if len(body.password) < 12:
        raise HTTPException(422, "Password must contain at least 12 characters")
    with Session() as db:
        if db.scalar(select(User).where(User.email == body.email)):
            raise HTTPException(409, "Email already exists")
        db.add(
            User(
                email=body.email, password=hash_password(body.password), role=body.role
            )
        )
        db.commit()
    audit(user.id, "create_user")
    return {"ok": True}


@app.get("/api/factories")
def factories(user=Depends(current)):
    with Session() as db:
        return [
            {"id": f.id, "name": f.name, "config": f.config}
            for f in db.scalars(select(Factory))
        ]


@app.post("/api/factories")
def save_factory(body: Config, user=Depends(editor)):
    with Session() as db:
        f = Factory(name=body.name, config=body.model_dump())
        db.add(f)
        db.commit()
        audit(user.id, "save_factory")
        return {"id": f.id}


@app.get("/api/datasets")
def datasets(user=Depends(current)):
    with Session() as db:
        return [
            {
                "id": d.id,
                "name": d.name,
                "source": d.source,
                "metadata": d.metadata_json,
                "count": len(d.rows),
            }
            for d in db.scalars(select(Dataset))
        ]


@app.post("/api/datasets/import")
async def upload(
    file: UploadFile = File(...),
    timezone: str = Form("UTC"),
    unit: str = Form("kW"),
    outliers: str = Form("reject"),
    user=Depends(editor),
):
    try:
        f, meta = ingest(await file.read(5_000_001), timezone, unit, outliers)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    with Session() as db:
        d = Dataset(
            name=(file.filename or "Imported CSV")[:120],
            source="imported",
            metadata_json=meta,
            rows=f.to_dict("records"),
        )
        db.add(d)
        db.commit()
        audit(user.id, "import_dataset")
        return {"id": d.id, "metadata": meta}


@app.get("/api/datasets/{dataset_id}/csv")
def dataset_csv(dataset_id: int, user=Depends(current)):
    with Session() as db:
        d = db.get(Dataset, dataset_id)
        if not d:
            raise HTTPException(404, "Dataset not found")
        return Response(
            pd.DataFrame(d.rows).to_csv(index=False),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="dataset-{d.id}.csv"'
            },
        )


class Job(BaseModel):
    kind: Literal["forecast", "optimization", "scenario"] = "optimization"
    dataset_id: int
    config: Config = Field(default_factory=Config)
    horizon: Literal[24, 168] = 24
    changes: dict = Field(default_factory=dict)
    forecast_id: int | None = None


@app.post("/api/runs", status_code=202)
def create_run(body: Job, user=Depends(editor)):
    try:
        Config(**{**body.config.model_dump(), **body.changes})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with Session() as db:
        if not db.get(Dataset, body.dataset_id):
            raise HTTPException(404, "Dataset not found")
        run = Run(
            kind=body.kind,
            dataset_id=body.dataset_id,
            user_id=user.id,
            request=body.model_dump(),
            result={},
        )
        db.add(run)
        db.commit()
        rid = run.id
    try:
        enqueue(rid)
    except Exception:
        with Session() as db:
            r = db.get(Run, rid)
            r.status = "failed"
            r.result = {"error": "Job queue unavailable"}
            db.commit()
        raise HTTPException(503, "Job queue unavailable")
    audit(user.id, f"create_{body.kind}:{rid}")
    return {"id": rid}


@app.get("/api/runs")
def runs(user=Depends(current)):
    with Session() as db:
        return [
            {"id": r.id, "kind": r.kind, "status": r.status, "created": str(r.created)}
            for r in db.scalars(select(Run).order_by(Run.id.desc()).limit(100))
        ]


@app.get("/api/runs/{rid}")
def run(rid: int, user=Depends(current)):
    with Session() as db:
        r = db.get(Run, rid)
        if not r:
            raise HTTPException(404, "Run not found")
        return {
            "id": r.id,
            "kind": r.kind,
            "status": r.status,
            "result": r.result,
            "request": r.request,
        }


def snapshot(p, db):
    r = db.get(Run, p.run_id)
    rows = r.result["baseline"]["optimized"]["rows"]
    if p.playing:
        steps = int((time.time() - p.updated) * p.speed)
        if steps:
            p.cursor = min(len(rows) - 1, p.cursor + steps)
            p.updated += steps / p.speed
        if p.cursor == len(rows) - 1:
            p.playing = False
        db.commit()
    return {
        "id": p.id,
        "run_id": p.run_id,
        "cursor": p.cursor,
        "count": len(rows),
        "playing": p.playing,
        "speed": p.speed,
        "current": rows[p.cursor],
    }


@app.post("/api/simulations/{rid}")
def simulation(rid: int, user=Depends(editor)):
    with Session() as db:
        r = db.get(Run, rid)
        if not r or r.status != "complete" or "baseline" not in r.result:
            raise HTTPException(422, "Completed dispatch required")
        p = Playback(run_id=rid, updated=time.time())
        db.add(p)
        db.commit()
        return snapshot(p, db)


class Control(BaseModel):
    action: Literal["start", "pause", "resume", "reset", "speed", "seek"]
    value: int = Field(1, ge=0, le=672)


@app.post("/api/simulations/{sid}/control")
def control(sid: int, body: Control, user=Depends(editor)):
    with Session() as db:
        p = db.get(Playback, sid)
        if not p:
            raise HTTPException(404, "Simulation not found")
        state = snapshot(p, db)
        if body.action in ("start", "resume"):
            p.playing = True
        elif body.action == "pause":
            p.playing = False
        elif body.action == "reset":
            p.cursor = 0
            p.playing = False
        elif body.action == "seek":
            p.cursor = min(body.value, state["count"] - 1)
            p.playing = False
        elif body.action == "speed":
            p.speed = max(1, min(60, body.value))
        p.updated = time.time()
        db.commit()
        audit(user.id, f"simulation_{body.action}:{sid}")
        return snapshot(p, db)


@app.get("/api/simulations/{sid}/events")
async def events(sid: int, user=Depends(current)):
    with Session() as db:
        if not db.get(Playback, sid):
            raise HTTPException(404, "Simulation not found")

    async def stream():
        for _ in range(300):
            with Session() as db:
                data = snapshot(db.get(Playback, sid), db)
            yield "data: " + json.dumps(data) + "\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


@app.get("/api/reports/{rid}")
def report(
    rid: int,
    format: Literal["csv", "pdf"] = "csv",
    period: Literal["daily", "weekly", "monthly", "forecast", "scenario"] = "daily",
    user=Depends(current),
):
    with Session() as db:
        r = db.get(Run, rid)
        if not r or r.status != "complete":
            raise HTTPException(404, "Completed run not found")
        if r.kind == "forecast":
            frame = pd.DataFrame(r.result["test"])
        elif period == "scenario" and "difference" in r.result:
            frame = pd.DataFrame(
                [
                    {
                        "metric": k,
                        "baseline": r.result["baseline"]["optimized"]["metrics"][k],
                        "modified": r.result["modified"]["optimized"]["metrics"][k],
                        "difference": v,
                    }
                    for k, v in r.result["difference"].items()
                ]
            )
        else:
            frame = pd.DataFrame(r.result["baseline"]["optimized"]["rows"])
            frame["timestamp"] = pd.to_datetime(frame.timestamp, utc=True)
            dt = r.result["baseline"]["optimized"]["interval_hours"]
            for col in ("grid_import", "solar", "unserved"):
                frame[col + "_kwh"] = frame[col + "_kw"] * dt
            frame = (
                frame.set_index("timestamp")
                .resample(
                    {"daily": "D", "weekly": "W", "monthly": "MS"}.get(period, "D")
                )
                .agg(
                    {
                        "cost": "sum",
                        "grid_import_kwh": "sum",
                        "solar_kwh": "sum",
                        "unserved_kwh": "sum",
                        "grid_import_kw": "max",
                    }
                )
                .reset_index()
            )
        audit(user.id, f"report:{rid}:{format}")
        filename = f"gridmind-{period}-{rid}.{format}"
        headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
        if format == "csv":
            return Response(
                frame.to_csv(index=False), media_type="text/csv", headers=headers
            )
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Table,
            TableStyle,
            Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet
        from xml.sax.saxutils import escape

        buf = io.BytesIO()
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4), rightMargin=25, leftMargin=25
        )
        story = [
            Paragraph(
                f"GRIDMIND · {period.title()} report · Run {rid}", styles["Title"]
            ),
            Paragraph(
                "Stored simulation results. USD, kW, kWh. Coverage is limited to the stored run horizon; no extrapolation to a full month. Grid carbon factor is scenario-configured (default 0.4 kg CO2/kWh).",
                styles["BodyText"],
            ),
            Spacer(1, 16),
        ]
        data = [[Paragraph(escape(str(c)), styles["BodyText"]) for c in frame.columns]]
        for row in frame.itertuples(index=False, name=None):
            data.append(
                [
                    Paragraph(
                        escape(f"{v:.3f}" if isinstance(v, float) else str(v)),
                        styles["BodyText"],
                    )
                    for v in row
                ]
            )
        table = Table(
            data,
            repeatRows=1,
            colWidths=[740 / len(frame.columns)] * len(frame.columns),
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d5f2e5")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        return Response(buf.getvalue(), media_type="application/pdf", headers=headers)


@app.get("/api/audit")
def logs(user=Depends(admin)):
    with Session() as db:
        return [
            {"action": a.action, "user_id": a.user_id, "created": str(a.created)}
            for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100))
        ]
