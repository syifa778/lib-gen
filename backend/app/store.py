from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any


def pdf_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def default_data_dir() -> Path:
    override = os.getenv("LIBGEN_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "data"


class Store:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.upload_dir = self.data_dir / "uploads"
        self.db_path = self.data_dir / "libgen.sqlite3"
        self._lock = Lock()
        self._ensure_dirs()
        self._init_schema()
        self._backfill_content_hashes()

    def _ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = DELETE")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    page_count INTEGER,
                    status TEXT NOT NULL,
                    error TEXT,
                    text TEXT NOT NULL DEFAULT '',
                    content_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_documents (
                    project_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    PRIMARY KEY (project_id, document_id),
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_id) REFERENCES documents(id)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )
            conn.commit()
            columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}
            if "content_hash" not in columns:
                conn.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash
                ON documents(content_hash)
                WHERE content_hash IS NOT NULL
                """
            )
            conn.commit()

    def _backfill_content_hashes(self) -> None:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM documents
                WHERE content_hash IS NULL OR content_hash = ''
                """
            ).fetchall()
        for row in rows:
            data = self.read_pdf(row["id"])
            if not data:
                continue
            digest = pdf_content_hash(data)
            with self._lock, self._connect() as conn:
                try:
                    conn.execute(
                        "UPDATE documents SET content_hash = ? WHERE id = ?",
                        (digest, row["id"]),
                    )
                    conn.commit()
                except sqlite3.IntegrityError:
                    conn.rollback()

    def pdf_path(self, doc_id: str) -> Path:
        return self.upload_dir / f"{doc_id}.pdf"

    def save_pdf(self, doc_id: str, data: bytes) -> Path:
        path = self.pdf_path(doc_id)
        path.write_bytes(data)
        return path

    def read_pdf(self, doc_id: str) -> bytes | None:
        path = self.pdf_path(doc_id)
        if not path.is_file():
            return None
        return path.read_bytes()

    def put_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (
                    id, filename, page_count, status, error, text, content_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc["id"],
                    doc["filename"],
                    doc.get("page_count"),
                    doc["status"],
                    doc.get("error"),
                    doc.get("text") or "",
                    doc.get("content_hash"),
                    doc["created_at"],
                    doc["updated_at"],
                ),
            )
            conn.commit()
        return self.get_document(doc["id"]) or dict(doc)

    def update_document(self, doc_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"filename", "page_count", "status", "error", "text", "content_hash", "updated_at"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_document(doc_id)
        assignments = ", ".join(f"{col} = ?" for col in updates)
        values = list(updates.values()) + [doc_id]
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE documents SET {assignments} WHERE id = ?",
                values,
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get_document(doc_id)

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
        return _document_from_row(row) if row else None

    def find_by_content_hash(self, digest: str) -> dict[str, Any] | None:
        if not digest:
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE content_hash = ?",
                (digest,),
            ).fetchone()
        return _document_from_row(row) if row else None

    def list_documents(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return [public_document(_document_from_row(row)) for row in rows]

    def pending_document_ids(self) -> list[str]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM documents
                WHERE status NOT IN ('ready', 'failed')
                """
            ).fetchall()
        return [row["id"] for row in rows]

    def put_project(self, project: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    project["id"],
                    project["name"],
                    project["created_at"],
                    project["updated_at"],
                ),
            )
            _replace_project_documents(conn, project["id"], project.get("document_ids") or [])
            conn.commit()
        return self.get_project(project["id"]) or dict(project)

    def update_project(self, project_id: str, **fields: Any) -> dict[str, Any] | None:
        if not self.get_project(project_id):
            return None
        name = fields.get("name")
        updated_at = fields.get("updated_at")
        document_ids = fields.get("document_ids")
        with self._lock, self._connect() as conn:
            sets = []
            values: list[Any] = []
            if name is not None:
                sets.append("name = ?")
                values.append(name)
            if updated_at is not None:
                sets.append("updated_at = ?")
                values.append(updated_at)
            if sets:
                values.append(project_id)
                conn.execute(
                    f"UPDATE projects SET {', '.join(sets)} WHERE id = ?",
                    values,
                )
            if document_ids is not None:
                _replace_project_documents(conn, project_id, document_ids)
            conn.commit()
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            doc_rows = conn.execute(
                """
                SELECT document_id FROM project_documents
                WHERE project_id = ?
                ORDER BY position
                """,
                (project_id,),
            ).fetchall()
            msg_rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE project_id = ?
                ORDER BY created_at, rowid
                """,
                (project_id,),
            ).fetchall()
        project = _project_from_row(row)
        project["document_ids"] = [item["document_id"] for item in doc_rows]
        project["messages"] = [_message_from_row(item) for item in msg_rows]
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at DESC"
            ).fetchall()
            items = []
            for row in rows:
                project = _project_from_row(row)
                doc_rows = conn.execute(
                    """
                    SELECT document_id FROM project_documents
                    WHERE project_id = ?
                    ORDER BY position
                    """,
                    (row["id"],),
                ).fetchall()
                count_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM messages WHERE project_id = ?",
                    (row["id"],),
                ).fetchone()
                project["document_ids"] = [item["document_id"] for item in doc_rows]
                project["message_count"] = count_row["n"] if count_row else 0
                items.append(public_project(project))
        return items

    def delete_project(self, project_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return cur.rowcount > 0

    def append_messages(self, project_id: str, messages: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not self.get_project(project_id):
            return None
        with self._lock, self._connect() as conn:
            for message in messages:
                conn.execute(
                    """
                    INSERT INTO messages (
                        id, project_id, role, content, citations, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message["id"],
                        project_id,
                        message["role"],
                        message["content"],
                        json.dumps(message.get("citations") or []),
                        message["created_at"],
                    ),
                )
            conn.commit()
        return self.get_project(project_id)

    def resume_pending(self) -> None:
        import threading

        from .services import process_document

        for doc_id in self.pending_document_ids():
            threading.Thread(target=process_document, args=(doc_id,), daemon=True).start()


def _replace_project_documents(
    conn: sqlite3.Connection, project_id: str, document_ids: list[str]
) -> None:
    conn.execute(
        "DELETE FROM project_documents WHERE project_id = ?",
        (project_id,),
    )
    conn.executemany(
        """
        INSERT INTO project_documents (project_id, document_id, position)
        VALUES (?, ?, ?)
        """,
        [(project_id, doc_id, index) for index, doc_id in enumerate(document_ids)],
    )


def _document_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "page_count": row["page_count"],
        "status": row["status"],
        "error": row["error"],
        "text": row["text"] or "",
        "content_hash": row["content_hash"] if "content_hash" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _project_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "document_ids": [],
        "messages": [],
    }


def _message_from_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        citations = json.loads(row["citations"] or "[]")
    except json.JSONDecodeError:
        citations = []
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "citations": citations,
        "created_at": row["created_at"],
    }


def public_document(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc["id"],
        "filename": doc["filename"],
        "page_count": doc.get("page_count"),
        "status": doc["status"],
        "error": doc.get("error"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project["id"],
        "name": project["name"],
        "document_ids": list(project.get("document_ids") or []),
        "created_at": project.get("created_at"),
        "updated_at": project.get("updated_at"),
        "message_count": project.get("message_count", len(project.get("messages") or [])),
    }


store = Store()
