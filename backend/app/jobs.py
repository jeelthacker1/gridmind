import os, logging
import pandas as pd
from .db import Session, Run, Dataset, ScenarioEvent
from .energy import Config, compare
from .forecast import forecast


def execute(run_id):
    with Session() as db:
        run = db.get(Run, run_id)
        run.status = "running"
        db.commit()
        try:
            f = pd.DataFrame(db.get(Dataset, run.dataset_id).rows)
            req = run.request
            if run.kind == "forecast":
                result = forecast(f, req.get("horizon", 24))
            else:
                cfg = Config(**req["config"])
                horizon = req.get("horizon", 24)
                minutes = int(
                    (
                        pd.to_datetime(f.timestamp.iloc[1])
                        - pd.to_datetime(f.timestamp.iloc[0])
                    ).total_seconds()
                    / 60
                )
                if req.get("forecast_id"):
                    prior = db.get(Run, req["forecast_id"])
                    if (
                        not prior
                        or prior.kind != "forecast"
                        or prior.status != "complete"
                        or prior.dataset_id != run.dataset_id
                    ):
                        raise ValueError(
                            "Select a completed forecast from the same dataset"
                        )
                    future = pd.DataFrame(prior.result["future"])
                    if len(future) < horizon * 60 // minutes:
                        raise ValueError("Forecast horizon is too short")
                    f = future.iloc[: horizon * 60 // minutes].copy()
                    # Tariff repeats the most recent observed week by UTC weekday/hour/minute.
                    source = pd.DataFrame(db.get(Dataset, run.dataset_id).rows)
                    for col in ("import_price", "export_price"):
                        history = list(source[col])
                        f[col] = [
                            history[-7 * 1440 // minutes + i % (7 * 1440 // minutes)]
                            for i in range(len(f))
                        ]
                    input_kind = "forecast"
                else:
                    f = f.iloc[-horizon * 60 // minutes :].copy()
                    input_kind = "historical replay"
                result = {
                    "baseline": compare(f, cfg),
                    "input_kind": input_kind,
                    "config": cfg.model_dump(),
                }
                if run.kind == "scenario":
                    changed = Config(**{**cfg.model_dump(), **req.get("changes", {})})
                    result["modified"] = compare(f, changed)
                    result["changes"] = req["changes"]
                    a = result["baseline"]["optimized"]["metrics"]
                    b = result["modified"]["optimized"]["metrics"]
                    result["difference"] = {k: b[k] - a[k] for k in a}
                    db.add(ScenarioEvent(run_id=run.id, changes=req["changes"]))
            run.result = result
            run.status = "complete"
        except Exception as exc:
            logging.exception("job failed", extra={"run_id": run_id})
            run.result = {"error": str(exc)}
            run.status = "failed"
        db.commit()


def enqueue(run_id):
    if os.getenv("JOB_MODE", "redis") == "inline":
        execute(run_id)
    else:
        from redis import Redis
        from rq import Queue

        Queue(
            connection=Redis.from_url(
                os.getenv("REDIS_URL", "redis://localhost:6379/0")
            )
        ).enqueue(execute, run_id, job_timeout=600)
