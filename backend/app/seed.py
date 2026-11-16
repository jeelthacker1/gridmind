import os, secrets
from sqlalchemy import select
from .db import Session, User, Factory, Dataset, Asset
from .energy import Config, synthetic, PROFILES
from .security import hash_password


def seed():
    with Session() as db:
        if not db.scalar(select(User).limit(1)):
            password = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(18)
            for role in ("admin", "analyst", "viewer"):
                db.add(
                    User(
                        email=f"{role}@gridmind.local",
                        password=hash_password(password),
                        role=role,
                    )
                )
            # First-run credential stays in local container logs, never the repository.
            print(f"GRIDMIND initial demo password: {password}", flush=True)
        if not db.scalar(select(Factory).limit(1)):
            for profile, (_, solar, capacity) in PROFILES.items():
                cfg = Config(
                    name={
                        "small": "Small manufacturing",
                        "medium": "Medium industrial",
                        "warehouse": "Solar-rich warehouse",
                    }[profile],
                    profile=profile,
                    capacity=capacity,
                    power=capacity * 0.4,
                )
                factory = Factory(name=cfg.name, config=cfg.model_dump())
                db.add(factory)
                db.flush()
                for kind, config in (
                    ("solar", {"rated_kw": solar}),
                    ("battery", {"capacity_kwh": capacity}),
                    ("grid", {"islandable": True}),
                    ("loads", {"critical_fraction": 0.65}),
                ):
                    db.add(
                        Asset(factory_id=factory.id, kind=kind, configuration=config)
                    )
                for minutes in (60, 15):
                    db.add(
                        Dataset(
                            name=f"{cfg.name} · {minutes}min",
                            source="synthetic",
                            metadata_json={
                                "seed": 42,
                                "profile": profile,
                                "minutes": minutes,
                                "version": 1,
                                "timezone": "UTC",
                            },
                            rows=synthetic(profile, minutes=minutes).to_dict("records"),
                        )
                    )
        db.commit()


if __name__ == "__main__":
    seed()
