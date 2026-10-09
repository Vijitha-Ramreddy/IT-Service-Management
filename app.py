import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
import uvicorn

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "it_service_management.db"
DEFAULT_DB_URL = f"sqlite:///{DB_PATH}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

app = FastAPI(title="IT Service Management API")

VALID_STATUS_NAMES = ["New", "Assigned", "In Progress", "On Hold", "Resolved", "Closed"]
ALLOWED_TRANSITIONS = {
    "New": {"Assigned", "In Progress"},
    "Assigned": {"In Progress", "On Hold"},
    "In Progress": {"On Hold"},
    "On Hold": {"Assigned", "In Progress"},
    "Resolved": set(),
    "Closed": set(),
}


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class RequestCreate(BaseModel):
    requester_id: int = Field(..., gt=0)
    category_id: int = Field(..., gt=0)
    priority_id: int = Field(..., gt=0)
    sla_policy_id: int = Field(..., gt=0)
    subject: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10, max_length=20000)
    assigned_agent_id: int | None = None
    due_at: datetime | None = None
    attachments: list[str] | None = None

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("subject must not be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description must not be empty")
        return cleaned


class RequestUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=10, max_length=20000)
    category_id: int | None = Field(default=None, gt=0)
    priority_id: int | None = Field(default=None, gt=0)
    sla_policy_id: int | None = Field(default=None, gt=0)
    due_at: datetime | None = None
    assigned_agent_id: int | None = None
    status: str | None = None

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("subject must not be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description must not be empty")
        return cleaned


class AssignmentRequest(BaseModel):
    assignee_id: int = Field(..., gt=0)
    reason: str | None = Field(default=None, max_length=255)


class StatusUpdate(BaseModel):
    status: str = Field(..., min_length=2, max_length=30)
    reason: str | None = Field(default=None, max_length=255)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in VALID_STATUS_NAMES:
            raise ValueError(f"status must be one of: {', '.join(VALID_STATUS_NAMES)}")
        return normalized


class ResolveRequest(BaseModel):
    resolution_details: str = Field(..., min_length=5, max_length=2000)
    resolved_by: int | None = None

    @field_validator("resolution_details")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("resolution_details must not be empty")
        return cleaned


class CloseRequest(BaseModel):
    closed_by: int | None = None
    reason: str | None = Field(default=None, max_length=255)


class RequestOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    request_number: str
    requester_id: int
    assigned_agent_id: int | None = None
    category_id: int
    priority_id: int
    status: str
    sla_policy_id: int
    subject: str
    description: str
    attachments: list[str] | None = None
    due_at: str | None = None
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    closed_at: str | None = None
    resolution_details: str | None = None


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL.replace("sqlite:///", "") if DATABASE_URL.startswith("sqlite:///") else DATABASE_URL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _load_seed_data(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO users (id, employee_code, full_name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "EMP-1001", "Alice Johnson", "alice.johnson@company.com", "temporary_hash_1", "EMPLOYEE", 1),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (id, employee_code, full_name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (2, "IT-2001", "Bob Smith", "bob.smith@company.com", "temporary_hash_2", "IT_AGENT", 1),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (id, employee_code, full_name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (3, "IT-2002", "Jane Lee", "jane.lee@company.com", "temporary_hash_3", "IT_AGENT", 1),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users (id, employee_code, full_name, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (4, "ADM-4001", "David Brown", "david.brown@company.com", "temporary_hash_4", "ADMIN", 1),
    )

    for name in ["Hardware", "Software", "Network", "Access", "Email", "Other"]:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))

    for name, sla_hours in [("Low", 72), ("Medium", 24), ("High", 8), ("Critical", 4)]:
        conn.execute("INSERT OR IGNORE INTO priorities (name, sla_hours) VALUES (?, ?)", (name, sla_hours))

    for name in VALID_STATUS_NAMES:
        conn.execute("INSERT OR IGNORE INTO statuses (name) VALUES (?)", (name,))

    for name in ["Standard", "Priority", "Executive"]:
        conn.execute("INSERT OR IGNORE INTO sla_policies (name, response_time_hours, resolution_time_hours) VALUES (?, ?, ?)", (name, 8, 24))

    conn.commit()


def ensure_schema() -> None:
    db_file = DATABASE_URL.replace("sqlite:///", "") if DATABASE_URL.startswith("sqlite:///") else DATABASE_URL
    if not db_file or db_file == ":memory:":
        return
    Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_file) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_code TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'EMPLOYEE' CHECK(role IN ('EMPLOYEE','IT_AGENT','MANAGER','ADMIN')),
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS priorities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sla_hours INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS statuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sla_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                response_time_hours INTEGER NOT NULL,
                resolution_time_hours INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT NOT NULL UNIQUE,
                requester_id INTEGER NOT NULL,
                assigned_agent_id INTEGER,
                category_id INTEGER NOT NULL,
                priority_id INTEGER NOT NULL,
                status_id INTEGER NOT NULL,
                sla_policy_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                attachments TEXT,
                due_at TEXT,
                assigned_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT,
                closed_at TEXT,
                resolved_by INTEGER,
                closed_by INTEGER,
                resolution_details TEXT,
                FOREIGN KEY(requester_id) REFERENCES users(id),
                FOREIGN KEY(assigned_agent_id) REFERENCES users(id),
                FOREIGN KEY(category_id) REFERENCES categories(id),
                FOREIGN KEY(priority_id) REFERENCES priorities(id),
                FOREIGN KEY(status_id) REFERENCES statuses(id),
                FOREIGN KEY(sla_policy_id) REFERENCES sla_policies(id)
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE,
                FOREIGN KEY(author_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS request_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                changed_by_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE,
                FOREIGN KEY(changed_by_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                from_status_id INTEGER,
                to_status_id INTEGER NOT NULL,
                changed_by_id INTEGER NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE,
                FOREIGN KEY(from_status_id) REFERENCES statuses(id),
                FOREIGN KEY(to_status_id) REFERENCES statuses(id),
                FOREIGN KEY(changed_by_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS assignment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                from_agent_id INTEGER,
                to_agent_id INTEGER NOT NULL,
                changed_by_id INTEGER NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE,
                FOREIGN KEY(from_agent_id) REFERENCES users(id),
                FOREIGN KEY(to_agent_id) REFERENCES users(id),
                FOREIGN KEY(changed_by_id) REFERENCES users(id)
            );
            """)

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_requests_request_number ON requests(request_number)")
        conn.commit()
        _load_seed_data(conn)


@app.on_event("startup")
async def startup_event() -> None:
    ensure_schema()


def ensure_request_exists(conn: sqlite3.Connection, request_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT r.*, s.name AS status_name FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE r.id = ?",
        (request_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Request {request_id} was not found")
    return row


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


def get_status_id(conn: sqlite3.Connection, status_name: str) -> int:
    row = conn.execute("SELECT id FROM statuses WHERE name = ?", (status_name,)).fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail=f"Unknown status: {status_name}")
    return int(row["id"])


def get_status_name(conn: sqlite3.Connection, status_id: int | None) -> str:
    if status_id is None:
        return "Unknown"
    row = conn.execute("SELECT name FROM statuses WHERE id = ?", (status_id,)).fetchone()
    return row["name"] if row else "Unknown"


def build_request_response(row: sqlite3.Row) -> dict[str, Any]:
    status_name = row["status_name"] if "status_name" in row.keys() and row["status_name"] is not None else "New"
    if "status_name" not in row.keys() and row["status_id"] is not None:
        with get_db_connection() as conn:
            status_name = get_status_name(conn, row["status_id"])

    sla_info = calculate_request_sla(row["id"])
    return {
        "id": row["id"],
        "request_number": row["request_number"],
        "requester_id": row["requester_id"],
        "assigned_agent_id": row["assigned_agent_id"],
        "category_id": row["category_id"],
        "priority_id": row["priority_id"],
        "status": status_name,
        "sla_policy_id": row["sla_policy_id"],
        "subject": row["subject"],
        "description": row["description"],
        "attachments": json_loads(row["attachments"]),
        "due_at": row["due_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "resolved_at": row["resolved_at"],
        "closed_at": row["closed_at"],
        "resolution_details": row["resolution_details"],
        "within_sla": sla_info["within_sla"],
        "sla_state": sla_info["state"],
        "sla_deadline": sla_info["deadline"],
        "sla_hours": sla_info["sla_hours"],
    }


def row_factory_priority(request_id: int):
    with get_db_connection() as conn:
        return conn.execute(
            "SELECT p.sla_hours FROM requests r JOIN priorities p ON p.id = r.priority_id WHERE r.id = ?",
            (request_id,),
        ).fetchone()


def json_loads(value: str | None) -> list[str] | None:
    if value in (None, ""):
        return None
    try:
        loaded = __import__("json").loads(value)
        return loaded if isinstance(loaded, list) else [loaded]
    except Exception:
        return None


def request_number_for(conn: sqlite3.Connection) -> str:
    while True:
        number = f"REQ-{datetime.utcnow().strftime('%Y%m%d')}-{__import__('uuid').uuid4().hex[:8].upper()}"
        existing = conn.execute("SELECT 1 FROM requests WHERE request_number = ?", (number,)).fetchone()
        if not existing:
            return number


def validate_assignee(conn: sqlite3.Connection, assignee_id: int) -> sqlite3.Row:
    assignee = get_user_by_id(conn, assignee_id)
    if assignee is None:
        raise HTTPException(status_code=400, detail=f"Assignee user {assignee_id} does not exist or is inactive")
    if assignee["role"] not in {"IT_AGENT", "ADMIN"}:
        raise HTTPException(status_code=400, detail="Only active IT agents or authorized administrators can be assigned")
    return assignee


def require_manager_or_admin(request) -> None:
    role = request.headers.get("x-user-role") or request.headers.get("X-User-Role") or request.query_params.get("role")
    if role is not None and role not in {"MANAGER", "ADMIN"}:
        raise HTTPException(status_code=403, detail="Manager or administrator access required")


def get_request_priority_sla(conn: sqlite3.Connection, request_row: sqlite3.Row) -> int:
    priority = conn.execute("SELECT sla_hours FROM priorities WHERE id = ?", (request_row["priority_id"],)).fetchone()
    if priority is None:
        return 0
    return int(priority["sla_hours"]) or 0


def calculate_request_sla(request_id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        row = conn.execute("SELECT r.*, s.name AS status_name FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE r.id = ?", (request_id,)).fetchone()
        if row is None:
            return {"sla_hours": 0, "deadline": None, "state": "UNKNOWN", "within_sla": None, "elapsed_seconds": 0, "hold_seconds": 0}

        priority_row = conn.execute("SELECT sla_hours FROM priorities WHERE id = ?", (row["priority_id"],)).fetchone()
        sla_hours = int(priority_row["sla_hours"]) if priority_row else 0
        created = parse_datetime(row["created_at"])
        if created is None:
            return {"sla_hours": sla_hours, "deadline": None, "state": "UNKNOWN", "within_sla": None, "elapsed_seconds": 0, "hold_seconds": 0}

        on_hold_id = conn.execute("SELECT id FROM statuses WHERE name = 'On Hold' LIMIT 1").fetchone()
        on_hold_seconds = 0
        if on_hold_id:
            history = conn.execute(
                "SELECT from_status_id, to_status_id, created_at FROM status_history WHERE request_id = ? ORDER BY created_at ASC",
                (request_id,),
            ).fetchall()
            hold_start = None
            for entry in history:
                from_status = entry["from_status_id"]
                to_status = entry["to_status_id"]
                timestamp = parse_datetime(entry["created_at"])
                if timestamp is None:
                    continue
                if to_status == on_hold_id["id"]:
                    hold_start = timestamp
                elif from_status == on_hold_id["id"] and hold_start is not None:
                    on_hold_seconds += (timestamp - hold_start).total_seconds()
                    hold_start = None
            if hold_start is not None and row["status_id"] == on_hold_id["id"]:
                now_ts = datetime.now(timezone.utc)
                on_hold_seconds += (now_ts - hold_start).total_seconds()

        now_ts = datetime.now(timezone.utc)
        elapsed_seconds = (now_ts - created).total_seconds() - on_hold_seconds if row["resolved_at"] is None else (parse_datetime(row["resolved_at"]) - created).total_seconds() - on_hold_seconds
        deadline = created + timedelta(hours=sla_hours) + timedelta(seconds=on_hold_seconds)
        threshold = sla_hours * 3600 * 0.8

        if row["resolved_at"] is not None:
            state = "RESOLVED_WITHIN_SLA" if (parse_datetime(row["resolved_at"]) - created).total_seconds() - on_hold_seconds <= sla_hours * 3600 else "BREACHED"
            within_sla = state == "RESOLVED_WITHIN_SLA"
        elif elapsed_seconds >= sla_hours * 3600:
            state = "BREACHED"
            within_sla = False
        elif elapsed_seconds >= threshold:
            state = "APPROACHING_BREACH"
            within_sla = True
        else:
            state = "WITHIN_SLA"
            within_sla = True

        return {
            "sla_hours": sla_hours,
            "deadline": deadline.isoformat().replace("+00:00", "Z"),
            "state": state,
            "within_sla": within_sla,
            "elapsed_seconds": elapsed_seconds,
            "hold_seconds": on_hold_seconds,
        }


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/users")
async def list_users(request: Request, include_inactive: bool = False):
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        filter_sql = " WHERE 1=1 " + ("" if include_inactive else " AND is_active = 1 ")
        rows = conn.execute(f"SELECT id, employee_code, full_name, email, role, is_active FROM users{filter_sql} ORDER BY full_name ASC").fetchall()
        return {"items": [dict(row) for row in rows], "total": len(rows)}


@app.get("/api/v1/users/agents")
async def list_agents() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, employee_code, full_name, email, role FROM users WHERE is_active = 1 AND role IN ('IT_AGENT', 'ADMIN') ORDER BY full_name ASC"
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/categories")
async def list_categories() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id, name, description, is_active FROM categories WHERE is_active = 1 ORDER BY name ASC").fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/priorities")
async def list_priorities() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id, name, sla_hours, description, is_active FROM priorities WHERE is_active = 1 ORDER BY sla_hours ASC").fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/statuses")
async def list_statuses() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id, name, description, is_active FROM statuses WHERE is_active = 1 ORDER BY id ASC").fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/sla-policies")
async def list_sla_policies() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id, name, response_time_hours, resolution_time_hours, description, is_active FROM sla_policies WHERE is_active = 1 ORDER BY name ASC").fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.post("/api/v1/requests", status_code=status.HTTP_201_CREATED)
async def create_request(payload: RequestCreate) -> dict[str, Any]:
    with get_db_connection() as conn:
        requester = get_user_by_id(conn, payload.requester_id)
        if requester is None:
            raise HTTPException(status_code=400, detail=f"Requester {payload.requester_id} does not exist or is inactive")
        category = conn.execute("SELECT id FROM categories WHERE id = ?", (payload.category_id,)).fetchone()
        if category is None:
            raise HTTPException(status_code=400, detail=f"Category {payload.category_id} was not found")
        priority = conn.execute("SELECT id, sla_hours FROM priorities WHERE id = ?", (payload.priority_id,)).fetchone()
        if priority is None:
            raise HTTPException(status_code=400, detail=f"Priority {payload.priority_id} was not found")
        sla_policy = conn.execute("SELECT id FROM sla_policies WHERE id = ?", (payload.sla_policy_id,)).fetchone()
        if sla_policy is None:
            raise HTTPException(status_code=400, detail=f"SLA policy {payload.sla_policy_id} was not found")

        initial_status_id = get_status_id(conn, "New")
        requested_due_at = payload.due_at.isoformat() if payload.due_at else None
        attachments_json = __import__("json").dumps(payload.attachments) if payload.attachments else None
        number = request_number_for(conn)

        cur = conn.execute(
            """
            INSERT INTO requests (
                request_number, requester_id, assigned_agent_id, category_id, priority_id,
                status_id, sla_policy_id, subject, description, attachments, due_at,
                assigned_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                number,
                payload.requester_id,
                payload.assigned_agent_id,
                payload.category_id,
                payload.priority_id,
                initial_status_id,
                payload.sla_policy_id,
                payload.subject,
                payload.description,
                attachments_json,
                requested_due_at,
                None,
            ),
        )
        request_id = cur.lastrowid

        if payload.assigned_agent_id is not None:
            validate_assignee(conn, payload.assigned_agent_id)
            conn.execute(
                "UPDATE requests SET assigned_at = ?, status_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (now_iso(), get_status_id(conn, "Assigned"), request_id),
            )
            conn.execute(
                "INSERT INTO assignment_history (request_id, from_agent_id, to_agent_id, changed_by_id, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, None, payload.assigned_agent_id, payload.requester_id, "Initial assignment", now_iso()),
            )
            conn.execute(
                "INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (request_id, initial_status_id, get_status_id(conn, "Assigned"), payload.requester_id, "Initial assignment", now_iso()),
            )

        conn.commit()
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
        return build_request_response(row)


@app.get("/api/v1/requests")
async def list_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    assignee_id: int | None = None,
    requester_id: int | None = None,
    sla_state: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    offset = (page - 1) * limit
    query = "SELECT r.*, s.name AS status_name FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE 1=1"
    params: list[Any] = []

    if status:
        query += " AND s.name = ?"
        params.append(status)
    if assignee_id is not None:
        query += " AND r.assigned_agent_id = ?"
        params.append(assignee_id)
    if requester_id is not None:
        query += " AND r.requester_id = ?"
        params.append(requester_id)
    if start_date:
        query += " AND r.created_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND r.created_at <= ?"
        params.append(end_date)

    with get_db_connection() as conn:
        rows = conn.execute(query + " ORDER BY r.created_at DESC LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
        filtered_rows = []
        for row in rows:
            if sla_state:
                current_state = calculate_request_sla(row["id"])["state"]
                if current_state != sla_state:
                    continue
            filtered_rows.append(build_request_response(row))

        total_query = "SELECT COUNT(*) AS total FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE 1=1"
        total_params: list[Any] = []
        if status:
            total_query += " AND s.name = ?"
            total_params.append(status)
        if assignee_id is not None:
            total_query += " AND r.assigned_agent_id = ?"
            total_params.append(assignee_id)
        if requester_id is not None:
            total_query += " AND r.requester_id = ?"
            total_params.append(requester_id)
        if start_date:
            total_query += " AND r.created_at >= ?"
            total_params.append(start_date)
        if end_date:
            total_query += " AND r.created_at <= ?"
            total_params.append(end_date)
        total = conn.execute(total_query, total_params).fetchone()["total"]

    return {
        "items": filtered_rows,
        "total": total,
        "page": page,
        "limit": limit,
    }


@app.get("/api/v1/requests/{id}")
async def get_request(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        row = ensure_request_exists(conn, id)
        return build_request_response(row)


@app.get("/api/v1/requests/{id}/sla")
async def get_request_sla(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
    sla = calculate_request_sla(id)
    return {
        "request_id": id,
        "sla_hours": sla["sla_hours"],
        "deadline": sla["deadline"],
        "state": sla["state"],
        "within_sla": sla["within_sla"],
        "elapsed_seconds": sla["elapsed_seconds"],
        "hold_seconds": sla["hold_seconds"],
    }


@app.post("/api/v1/requests/{id}/comments")
async def add_request_comment(id: int, payload: dict[str, Any]) -> dict[str, Any]:
    message = (payload.get("message") or "").strip()
    author_id = payload.get("author_id")
    if not message:
        raise HTTPException(status_code=400, detail="Comment message is required")
    if author_id is None:
        raise HTTPException(status_code=400, detail="author_id is required")

    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
        if get_user_by_id(conn, int(author_id)) is None:
            raise HTTPException(status_code=400, detail=f"User {author_id} does not exist or is inactive")
        conn.execute(
            "INSERT INTO comments (request_id, author_id, message, created_at) VALUES (?, ?, ?, ?)",
            (id, int(author_id), message, now_iso()),
        )
        conn.commit()

    return {"id": id, "message": message, "author_id": int(author_id), "created_at": now_iso()}


@app.get("/api/v1/requests/{id}/comments")
async def list_request_comments(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
        rows = conn.execute(
            "SELECT c.*, u.full_name AS author_name FROM comments c JOIN users u ON u.id = c.author_id WHERE c.request_id = ? ORDER BY c.created_at ASC",
            (id,),
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/requests/{id}/history")
async def list_request_history(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
        request_rows = conn.execute(
            "SELECT r.id AS request_id, r.changed_by_id, r.field_name, r.old_value, r.new_value, r.created_at, 'request' AS source FROM request_history r WHERE r.request_id = ? ORDER BY r.created_at ASC",
            (id,),
        ).fetchall()
        status_rows = conn.execute(
            "SELECT h.id AS history_id, h.changed_by_id, 'status' AS field_name, fs.name AS old_value, ts.name AS new_value, h.created_at, 'status' AS source FROM status_history h LEFT JOIN statuses fs ON fs.id = h.from_status_id LEFT JOIN statuses ts ON ts.id = h.to_status_id WHERE h.request_id = ? ORDER BY h.created_at ASC",
            (id,),
        ).fetchall()
        assignment_rows = conn.execute(
            "SELECT a.id AS request_id, a.changed_by_id, 'assignee' AS field_name, fu.full_name AS old_value, tu.full_name AS new_value, a.created_at, 'assignment' AS source FROM assignment_history a LEFT JOIN users fu ON fu.id = a.from_agent_id LEFT JOIN users tu ON tu.id = a.to_agent_id WHERE a.request_id = ? ORDER BY a.created_at ASC",
            (id,),
        ).fetchall()
        all_rows = [dict(row) for row in request_rows] + [dict(row) for row in status_rows] + [dict(row) for row in assignment_rows]
        all_rows.sort(key=lambda item: item.get("created_at") or "")
        return {"items": all_rows, "total": len(all_rows)}


@app.get("/api/v1/requests/{id}/status-history")
async def list_status_history(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
        rows = conn.execute(
            "SELECT h.*, fs.name AS from_status, ts.name AS to_status, u.full_name AS changed_by_name FROM status_history h LEFT JOIN statuses fs ON fs.id = h.from_status_id LEFT JOIN statuses ts ON ts.id = h.to_status_id LEFT JOIN users u ON u.id = h.changed_by_id WHERE h.request_id = ? ORDER BY h.created_at ASC",
            (id,),
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/requests/{id}/assignment-history")
async def list_assignment_history(id: int) -> dict[str, Any]:
    with get_db_connection() as conn:
        ensure_request_exists(conn, id)
        rows = conn.execute(
            "SELECT a.*, fu.full_name AS from_agent_name, tu.full_name AS to_agent_name, u.full_name AS changed_by_name FROM assignment_history a LEFT JOIN users fu ON fu.id = a.from_agent_id LEFT JOIN users tu ON tu.id = a.to_agent_id LEFT JOIN users u ON u.id = a.changed_by_id WHERE a.request_id = ? ORDER BY a.created_at ASC",
            (id,),
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.patch("/api/v1/requests/{id}")
async def update_request(id: int, payload: RequestUpdate) -> dict[str, Any]:
    with get_db_connection() as conn:
        row = ensure_request_exists(conn, id)
        if row["closed_at"] is not None:
            raise HTTPException(status_code=400, detail="Closed requests cannot be modified")

        updates: list[str] = []
        values: list[Any] = []

        if payload.subject is not None:
            updates.append("subject = ?")
            values.append(payload.subject)
        if payload.description is not None:
            updates.append("description = ?")
            values.append(payload.description)
        if payload.category_id is not None:
            updates.append("category_id = ?")
            values.append(payload.category_id)
        if payload.priority_id is not None:
            updates.append("priority_id = ?")
            values.append(payload.priority_id)
        if payload.sla_policy_id is not None:
            updates.append("sla_policy_id = ?")
            values.append(payload.sla_policy_id)
        if payload.due_at is not None:
            updates.append("due_at = ?")
            values.append(payload.due_at.isoformat())
        if payload.assigned_agent_id is not None:
            validate_assignee(conn, payload.assigned_agent_id)
            updates.append("assigned_agent_id = ?")
            values.append(payload.assigned_agent_id)
            updates.append("assigned_at = ?")
            values.append(now_iso())
            if row["status_id"] in {get_status_id(conn, "New"), get_status_id(conn, "Assigned")}:
                updates.append("status_id = ?")
                values.append(get_status_id(conn, "Assigned"))
        if payload.status is not None:
            new_status_id = get_status_id(conn, payload.status)
            if row["status_id"] == get_status_id(conn, "Closed"):
                raise HTTPException(status_code=400, detail="Cannot change a closed request")
            if payload.status not in ALLOWED_TRANSITIONS.get(get_status_name(conn, row["status_id"]), set()):
                raise HTTPException(status_code=400, detail=f"Status transition {get_status_name(conn, row['status_id'])} -> {payload.status} is not allowed")
            updates.append("status_id = ?")
            values.append(new_status_id)

        if not updates:
            raise HTTPException(status_code=400, detail="No valid fields were provided for update")

        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(id)
        cursor = conn.execute(f"UPDATE requests SET {', '.join(updates)} WHERE id = ?", values)
        if cursor.rowcount == 0:
            raise HTTPException(status_code=409, detail="Request could not be updated because it was modified concurrently")
        conn.commit()

        row = ensure_request_exists(conn, id)
        return build_request_response(row)


@app.post("/api/v1/requests/{id}/assign")
async def assign_request(id: int, payload: AssignmentRequest) -> dict[str, Any]:
    with get_db_connection() as conn:
        request_row = ensure_request_exists(conn, id)
        if request_row["closed_at"] is not None:
            raise HTTPException(status_code=400, detail="Closed requests cannot be assigned")

        assignee = validate_assignee(conn, payload.assignee_id)
        old_agent_id = request_row["assigned_agent_id"]
        current_status_name = get_status_name(conn, request_row["status_id"])
        next_status_name = "Assigned" if current_status_name in {"New", "Assigned"} else current_status_name

        with conn:
            cursor = conn.execute(
                "UPDATE requests SET assigned_agent_id = ?, assigned_at = ?, status_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND closed_at IS NULL",
                (payload.assignee_id, now_iso(), get_status_id(conn, next_status_name), id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="Request was updated concurrently; please retry")
            conn.execute(
                "INSERT INTO assignment_history (request_id, from_agent_id, to_agent_id, changed_by_id, reason, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, old_agent_id, payload.assignee_id, assignee["id"], payload.reason or "Assignment update", now_iso()),
            )
            if current_status_name != next_status_name:
                conn.execute(
                    "INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (id, request_row["status_id"], get_status_id(conn, next_status_name), assignee["id"], payload.reason or "Assignment update", now_iso()),
                )
            conn.commit()

        row = ensure_request_exists(conn, id)
        return build_request_response(row)


@app.get("/api/v1/users/agents")
async def list_agents() -> dict[str, Any]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, employee_code, full_name, email, role FROM users WHERE is_active = 1 AND role IN ('IT_AGENT', 'ADMIN') ORDER BY full_name ASC"
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/reports/unassigned")
async def list_unassigned(request: Request) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT r.*, s.name AS status_name FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE r.assigned_agent_id IS NULL AND r.closed_at IS NULL ORDER BY r.created_at DESC"
        ).fetchall()
        return {"items": [build_request_response(row) for row in rows], "total": len(rows)}


@app.get("/api/v1/reports/sla-breaches")
async def list_sla_breaches(request: Request) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT r.*, s.name AS status_name FROM requests r LEFT JOIN statuses s ON s.id = r.status_id ORDER BY r.created_at DESC"
        ).fetchall()
        filtered = []
        for row in rows:
            sla = calculate_request_sla(row["id"])
            if sla["state"] in {"APPROACHING_BREACH", "BREACHED"}:
                item = build_request_response(row)
                item["sla_state"] = sla["state"]
                item["sla_deadline"] = sla["deadline"]
                filtered.append(item)
        return {"items": filtered, "total": len(filtered)}


@app.get("/api/v1/reports/summary")
async def summary_report(request: Request, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        where = []
        params: list[Any] = []
        if start_date:
            where.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            where.append("created_at <= ?")
            params.append(end_date)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        total = conn.execute(f"SELECT COUNT(*) AS total FROM requests{where_sql}", params).fetchone()["total"]
        open_count = conn.execute(f"SELECT COUNT(*) AS total FROM requests r LEFT JOIN statuses s ON s.id = r.status_id WHERE s.name NOT IN ('Resolved', 'Closed'){where_sql}", params).fetchone()["total"]
        resolved = conn.execute(f"SELECT COUNT(*) AS total FROM requests WHERE resolved_at IS NOT NULL{where_sql}", params).fetchone()["total"]
        closed = conn.execute(f"SELECT COUNT(*) AS total FROM requests WHERE closed_at IS NOT NULL{where_sql}", params).fetchone()["total"]
        unassigned = conn.execute(f"SELECT COUNT(*) AS total FROM requests WHERE assigned_agent_id IS NULL AND closed_at IS NULL{where_sql}", params).fetchone()["total"]
        overdue = 0
        rows = conn.execute(f"SELECT * FROM requests{where_sql}", params).fetchall()
        for row in rows:
            sla = calculate_request_sla(row["id"])
            if sla["state"] == "BREACHED":
                overdue += 1

        approaching = 0
        breached = 0
        for row in rows:
            sla = calculate_request_sla(row["id"])
            if sla["state"] == "APPROACHING_BREACH":
                approaching += 1
            elif sla["state"] == "BREACHED":
                breached += 1

    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "closed": closed,
        "unassigned": unassigned,
        "overdue": overdue,
        "approaching_sla_breach": approaching,
        "sla_breaches": breached,
        "generated_at": now_iso(),
    }


@app.get("/api/v1/reports/by-priority")
async def report_by_priority(request: Request, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        where, params = build_report_where(start_date, end_date)
        rows = conn.execute(
            "SELECT p.name AS label, COUNT(r.id) AS count FROM requests r JOIN priorities p ON p.id = r.priority_id " + where + " GROUP BY p.name ORDER BY count DESC",
            params,
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/reports/by-category")
async def report_by_category(request: Request, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        where, params = build_report_where(start_date, end_date)
        rows = conn.execute(
            "SELECT c.name AS label, COUNT(r.id) AS count FROM requests r JOIN categories c ON c.id = r.category_id " + where + " GROUP BY c.name ORDER BY count DESC",
            params,
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/reports/by-status")
async def report_by_status(request: Request, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        where, params = build_report_where(start_date, end_date)
        rows = conn.execute(
            "SELECT s.name AS label, COUNT(r.id) AS count FROM requests r JOIN statuses s ON s.id = r.status_id " + where + " GROUP BY s.name ORDER BY count DESC",
            params,
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/v1/reports/by-assignee")
async def report_by_assignee(request: Request, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
    require_manager_or_admin(request)
    with get_db_connection() as conn:
        where, params = build_report_where(start_date, end_date)
        rows = conn.execute(
            "SELECT u.full_name AS label, COUNT(r.id) AS count FROM requests r LEFT JOIN users u ON u.id = r.assigned_agent_id " + where + " GROUP BY u.full_name ORDER BY count DESC",
            params,
        ).fetchall()
        return {"items": [dict(r) for r in rows], "total": len(rows)}


def build_report_where(start_date: str | None, end_date: str | None):
    clauses = []
    params: list[Any] = []
    if start_date:
        clauses.append("r.created_at >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("r.created_at <= ?")
        params.append(end_date)
    where_sql = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where_sql, params


@app.post("/api/v1/requests/{id}/status")
async def update_request_status(id: int, payload: StatusUpdate) -> dict[str, Any]:
    with get_db_connection() as conn:
        request_row = ensure_request_exists(conn, id)
        if request_row["closed_at"] is not None:
            raise HTTPException(status_code=400, detail="Cannot change the status of a closed request")

        current_status_name = get_status_name(conn, request_row["status_id"])
        if payload.status == "Closed" and request_row["resolved_at"] is None:
            raise HTTPException(status_code=400, detail="Direct closure is not allowed until the request is resolved")
        if payload.status == "In Progress" and request_row["assigned_agent_id"] is None:
            raise HTTPException(status_code=400, detail="Requests must be assigned before work can begin")

        allowed = ALLOWED_TRANSITIONS.get(current_status_name, set())
        if payload.status not in allowed:
            raise HTTPException(status_code=400, detail=f"Invalid status transition from {current_status_name} to {payload.status}")

        next_status_id = get_status_id(conn, payload.status)
        actor_id = request_row["requester_id"]
        with conn:
            cursor = conn.execute(
                "UPDATE requests SET status_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND closed_at IS NULL",
                (next_status_id, id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="Request was updated concurrently; please retry")
            conn.execute(
                "INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, request_row["status_id"], next_status_id, actor_id, payload.reason or f"Status changed to {payload.status}", now_iso()),
            )
            if payload.status == "On Hold":
                conn.execute(
                    "INSERT INTO request_history (request_id, changed_by_id, field_name, old_value, new_value, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (id, actor_id, "status", current_status_name, "On Hold", now_iso()),
                )
            elif current_status_name == "On Hold":
                conn.execute(
                    "INSERT INTO request_history (request_id, changed_by_id, field_name, old_value, new_value, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (id, actor_id, "hold_duration", "On Hold", payload.status, now_iso()),
                )
            conn.commit()

        row = ensure_request_exists(conn, id)
        return build_request_response(row)


@app.post("/api/v1/requests/{id}/resolve")
async def resolve_request(id: int, payload: ResolveRequest) -> dict[str, Any]:
    with get_db_connection() as conn:
        request_row = ensure_request_exists(conn, id)
        current_status_name = get_status_name(conn, request_row["status_id"])
        if request_row["closed_at"] is not None:
            raise HTTPException(status_code=400, detail="Closed requests cannot be resolved again")
        if request_row["resolved_at"] is not None:
            raise HTTPException(status_code=409, detail="This request has already been resolved")
        if current_status_name not in {"New", "Assigned", "In Progress", "On Hold"}:
            raise HTTPException(status_code=400, detail=f"Request cannot be resolved from status {current_status_name}")
        if not payload.resolution_details or not payload.resolution_details.strip():
            raise HTTPException(status_code=400, detail="resolution_details is required")

        resolved_by = payload.resolved_by or request_row["requester_id"]
        with conn:
            cursor = conn.execute(
                "UPDATE requests SET status_id = ?, resolved_at = ?, resolved_by = ?, resolution_details = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND resolved_at IS NULL",
                (get_status_id(conn, "Resolved"), now_iso(), resolved_by, payload.resolution_details.strip(), id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="Request status changed concurrently; please retry")
            conn.execute(
                "INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, request_row["status_id"], get_status_id(conn, "Resolved"), resolved_by, payload.resolution_details.strip(), now_iso()),
            )
            conn.execute(
                "INSERT INTO request_history (request_id, changed_by_id, field_name, old_value, new_value, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, resolved_by, "resolution_details", request_row["resolution_details"], payload.resolution_details.strip(), now_iso()),
            )
            conn.commit()

        row = ensure_request_exists(conn, id)
        return build_request_response(row)


@app.post("/api/v1/requests/{id}/close")
async def close_request(id: int, payload: CloseRequest) -> dict[str, Any]:
    with get_db_connection() as conn:
        request_row = ensure_request_exists(conn, id)
        if request_row["closed_at"] is not None:
            raise HTTPException(status_code=409, detail="This request is already closed")
        if request_row["resolved_at"] is None:
            raise HTTPException(status_code=400, detail="Request must be resolved before it can be closed")

        closed_by = payload.closed_by or request_row["requester_id"]
        with conn:
            cursor = conn.execute(
                "UPDATE requests SET status_id = ?, closed_at = ?, closed_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND closed_at IS NULL",
                (get_status_id(conn, "Closed"), now_iso(), closed_by, id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="Request was updated concurrently; please retry")
            conn.execute(
                "INSERT INTO status_history (request_id, from_status_id, to_status_id, changed_by_id, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, request_row["status_id"], get_status_id(conn, "Closed"), closed_by, payload.reason or "Request closed", now_iso()),
            )
            conn.execute(
                "INSERT INTO request_history (request_id, changed_by_id, field_name, old_value, new_value, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (id, closed_by, "closed_at", request_row["closed_at"], now_iso(), now_iso()),
            )
            conn.commit()

        row = ensure_request_exists(conn, id)
        return build_request_response(row)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
