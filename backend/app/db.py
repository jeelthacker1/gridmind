import os
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine,
    String,
    JSON,
    ForeignKey,
    DateTime,
    Integer,
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

engine = create_engine(
    os.getenv("DATABASE_URL", "sqlite:///./gridmind.db"), pool_pre_ping=True
)
Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("role IN ('admin','analyst','viewer')"),)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires: Mapped[float]


class Factory(Base):
    __tablename__ = "factories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    config: Mapped[dict] = mapped_column(JSON)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(20))
    metadata_json: Mapped[dict] = mapped_column(JSON)
    rows: Mapped[list] = mapped_column(JSON)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    request: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class Playback(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"))
    cursor: Mapped[int] = mapped_column(Integer, default=0)
    speed: Mapped[int] = mapped_column(Integer, default=1)
    playing: Mapped[bool] = mapped_column(default=False)
    updated: Mapped[float]


class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(200))
    created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, index=True
    )


class Asset(Base):
    __tablename__ = "energy_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    factory_id: Mapped[int] = mapped_column(ForeignKey("factories.id"))
    kind: Mapped[str] = mapped_column(String(30))
    configuration: Mapped[dict] = mapped_column(JSON)


class ScenarioEvent(Base):
    __tablename__ = "scenario_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    changes: Mapped[dict] = mapped_column(JSON)
