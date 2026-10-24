"""SQLite persistence and atomic ownership/version boundaries."""

from contextlib import contextmanager, closing
import json
from pathlib import Path
import re
import secrets
import sqlite3

from fastapi import HTTPException


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class Store:
    def __init__(self, path):
        self.path = str(Path(path).resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS trips(trip_id TEXT PRIMARY KEY,owner TEXT NOT NULL,version INTEGER NOT NULL,status TEXT NOT NULL,title TEXT NOT NULL,updated_at TEXT NOT NULL,state TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS trips_owner ON trips(owner,updated_at DESC);
                CREATE TABLE IF NOT EXISTS orders(order_id TEXT PRIMARY KEY,owner TEXT NOT NULL,trip_id TEXT NOT NULL UNIQUE,quote_id TEXT NOT NULL UNIQUE,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS idempotency(owner TEXT NOT NULL,key TEXT NOT NULL,request_hash TEXT NOT NULL,trip_id TEXT NOT NULL,order_id TEXT NOT NULL,response TEXT NOT NULL,PRIMARY KEY(owner,key));
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,trip_id TEXT NOT NULL,version INTEGER NOT NULL,body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_trip ON events(trip_id,id);
                CREATE TABLE IF NOT EXISTS preferences(owner TEXT PRIMARY KEY,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS service_requests(request_id TEXT PRIMARY KEY,owner TEXT NOT NULL,trip_id TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL);
            """)

    def connect(self):
        db = sqlite3.connect(
            self.path, timeout=10, isolation_level=None, check_same_thread=False
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def healthy(self):
        try:
            if not Path(self.path).is_file():
                return False
            with closing(self.connect()) as db:
                tables = {
                    row["name"]
                    for row in db.execute(
                        "SELECT name FROM sqlite_schema WHERE type='table'"
                    )
                }
                if not {
                    "sessions",
                    "trips",
                    "orders",
                    "idempotency",
                    "events",
                    "preferences",
                    "service_requests",
                }.issubset(tables):
                    return False
                db.execute("SELECT trip_id,version,state FROM trips LIMIT 1").fetchone()
            return True
        except (sqlite3.Error, OSError):
            return False

    @contextmanager
    def transaction(self, write=False):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def session(self, cookie, now):
        if cookie and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", cookie):
            with self.transaction() as db:
                if db.execute(
                    "SELECT 1 FROM sessions WHERE token=?", (cookie,)
                ).fetchone():
                    return cookie, False
        token = secrets.token_urlsafe(32)
        with self.transaction(write=True) as db:
            db.execute("INSERT INTO sessions VALUES(?,?)", (token, now.isoformat()))
        return token, True

    @staticmethod
    def owned(db, trip_id, owner):
        row = db.execute(
            "SELECT state FROM trips WHERE trip_id=? AND owner=?", (trip_id, owner)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Поездка недоступна в текущей сессии.")
        return json.loads(row["state"])

    def get(self, trip_id, owner):
        with self.transaction() as db:
            return self.owned(db, trip_id, owner)

    def history(self, owner):
        with self.transaction() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT trip_id,version,status,title,updated_at FROM trips WHERE owner=? ORDER BY updated_at DESC,rowid DESC",
                    (owner,),
                )
            ]

    @staticmethod
    def persist(db, state, owner, now, expected_version=None, trace_start=0):
        title = (
            state["plans"][0]["destination"]["name"]
            if state["plans"]
            else "Новая поездка"
        )
        if state.get("order"):
            title = state["order"]["plan"]["destination"]["name"]
        values = (
            state["version"],
            state["status"],
            title,
            now.isoformat(),
            encode(state),
        )
        if expected_version is None:
            db.execute(
                "INSERT INTO trips(version,status,title,updated_at,state,trip_id,owner) VALUES(?,?,?,?,?,?,?)",
                values + (state["trip_id"], owner),
            )
        else:
            count = db.execute(
                "UPDATE trips SET version=?,status=?,title=?,updated_at=?,state=? WHERE trip_id=? AND owner=? AND version=?",
                values + (state["trip_id"], owner, expected_version),
            ).rowcount
            if count != 1:
                raise HTTPException(
                    409,
                    "Поездка уже изменена. Обновите состояние и повторите действие.",
                )
        for action in state["action_trace"][trace_start:]:
            db.execute(
                "INSERT INTO events(trip_id,version,body) VALUES(?,?,?)",
                (
                    state["trip_id"],
                    state["version"],
                    encode({"type": "action", "version": state["version"], **action}),
                ),
            )
        db.execute(
            "INSERT INTO events(trip_id,version,body) VALUES(?,?,?)",
            (
                state["trip_id"],
                state["version"],
                encode(
                    {
                        "type": "state",
                        "version": state["version"],
                        "status": state["status"],
                        "detail": f"Состояние поездки сохранено: версия {state['version']}.",
                    }
                ),
            ),
        )

    def save(self, state, owner, now, expected_version=None, trace_start=0):
        with self.transaction(write=True) as db:
            if expected_version is not None:
                self.owned(db, state["trip_id"], owner)
            self.persist(db, state, owner, now, expected_version, trace_start)

    def events(self, trip_id, owner, after=0):
        with self.transaction() as db:
            self.owned(db, trip_id, owner)
            return [
                (r["id"], json.loads(r["body"]))
                for r in db.execute(
                    "SELECT id,body FROM events WHERE trip_id=? AND id>? ORDER BY id",
                    (trip_id, after),
                )
            ]

    def order(self, order_id, owner):
        with self.transaction() as db:
            row = db.execute(
                "SELECT body FROM orders WHERE order_id=? AND owner=?",
                (order_id, owner),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Демозаказ недоступен в текущей сессии.")
            return json.loads(row["body"])

    def preferences(self, owner):
        with self.transaction() as db:
            row = db.execute(
                "SELECT body FROM preferences WHERE owner=?", (owner,)
            ).fetchone()
            return json.loads(row["body"]) if row else {}

    def set_preferences(self, owner, value):
        with self.transaction(write=True) as db:
            if value:
                db.execute(
                    "INSERT INTO preferences VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET body=excluded.body",
                    (owner, encode(value)),
                )
            else:
                db.execute("DELETE FROM preferences WHERE owner=?", (owner,))
        return value
