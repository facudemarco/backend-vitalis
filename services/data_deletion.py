"""Helpers for previewing and removing a user's related database records."""

import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy import text


_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
_SIGNATURE_TABLES = {
    "medical_record_signatures",
    "medical_record_laboral_signatures",
    "medical_record_patient_signatures",
    "medical_record_medical_responsable_signatures",
}

_BASE_DIR = Path(__file__).resolve().parent.parent
SIGNATURES_DIR = Path(os.getenv("SIGNATURES_DIR", "/home/iweb/vitalis/data/signatures/" if os.name == "posix" else _BASE_DIR / "signatures"))
DATA_IMAGES_DIR = Path(os.getenv("DATA_IMAGES_DIR", _BASE_DIR / "data_images"))
STUDIES_DIR = Path(os.getenv("STUDIES_DIR", "/home/iweb/vitalis/data/studies/" if os.name == "posix" else _BASE_DIR / "studies"))


def _identifier(name: str) -> str:
    if not _IDENTIFIER.fullmatch(name):
        raise ValueError("Invalid SQL identifier")
    return f"`{name}`"


def _primary_key_columns(db, table: str) -> list[str]:
    return [
        row["COLUMN_NAME"]
        for row in db.execute(
            text("""
                SELECT COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table
                  AND CONSTRAINT_NAME = 'PRIMARY'
                ORDER BY ORDINAL_POSITION
            """),
            {"table": table},
        ).mappings().all()
    ]


def _child_foreign_keys(db, table: str) -> dict[tuple[str, str], list[dict[str, str]]]:
    rows = db.execute(
        text("""
            SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME, REFERENCED_COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
              AND REFERENCED_TABLE_SCHEMA = DATABASE()
              AND REFERENCED_TABLE_NAME = :table
            ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
        """),
        {"table": table},
    ).mappings().all()
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["TABLE_NAME"], row["CONSTRAINT_NAME"]), []).append({
            "column": row["COLUMN_NAME"],
            "referenced": row["REFERENCED_COLUMN_NAME"],
        })
    return groups


def _children(db, table: str, parent: dict[str, Any]):
    for (child_table, _constraint), columns in _child_foreign_keys(db, table).items():
        conditions = []
        params: dict[str, Any] = {}
        for index, column in enumerate(columns):
            key = f"ref_{index}"
            value = parent.get(column["referenced"])
            if value is None:
                break
            conditions.append(f"{_identifier(column['column'])} = :{key}")
            params[key] = value
        else:
            query = f"SELECT * FROM {_identifier(child_table)} WHERE " + " AND ".join(conditions)
            for child in db.execute(text(query), params).mappings().all():
                yield child_table, dict(child)


def _row_key(db, table: str, row: dict[str, Any]) -> tuple[Any, ...]:
    columns = _primary_key_columns(db, table)
    if not columns:
        raise RuntimeError(f"Cannot safely delete rows from {table}: primary key not found")
    return tuple(row[column] for column in columns)


def _walk(db, table: str, row: dict[str, Any], seen: set[tuple[str, tuple[Any, ...]]],
          counts: dict[str, int], files: list[tuple[Path, str]] | None = None,
          delete: bool = False) -> None:
    key = (table, _row_key(db, table, row))
    if key in seen:
        return
    seen.add(key)

    if counts is not None:
        counts[table] = counts.get(table, 0) + 1

    if files is not None:
        directory = STUDIES_DIR if table == "study_files" else (
            DATA_IMAGES_DIR if table == "medical_record_data_img" else (
                SIGNATURES_DIR if table in _SIGNATURE_TABLES else None
            )
        )
        file_value = row.get("file_path") if table == "study_files" else row.get("url")
        if directory is not None and file_value:
            files.append((directory, str(file_value)))

    for child_table, child_row in list(_children(db, table, row)):
        _walk(db, child_table, child_row, seen, counts, files, delete)

    if delete:
        columns = _primary_key_columns(db, table)
        where = " AND ".join(f"{_identifier(column)} = :pk_{i}" for i, column in enumerate(columns))
        params = {f"pk_{i}": row[column] for i, column in enumerate(columns)}
        db.execute(text(f"DELETE FROM {_identifier(table)} WHERE {where}"), params)


def _root_row(db, table: str, record_id: str) -> dict[str, Any] | None:
    return db.execute(
        text(f"SELECT * FROM {_identifier(table)} WHERE `id` = :id"),
        {"id": record_id},
    ).mappings().first()


def _walk_roots(db, roots: list[tuple[str, str]], delete: bool = False):
    seen: set[tuple[str, tuple[Any, ...]]] = set()
    counts: dict[str, int] = {}
    files: list[tuple[Path, str]] = []
    for table, record_id in roots:
        row = _root_row(db, table, record_id)
        if row:
            _walk(db, table, dict(row), seen, counts, files, delete)
    return counts, files


def summarize_related_records(db, roots: list[tuple[str, str]]) -> list[dict[str, Any]]:
    counts, _ = _walk_roots(db, roots)
    return [
        {"table": table, "count": count}
        for table, count in sorted(counts.items())
        if count
    ]


def _remove_files(files: list[tuple[Path, str]]) -> None:
    for directory, value in files:
        try:
            filename = Path(value.split("?", 1)[0]).name
            if filename:
                path = directory / filename
                if path.is_file():
                    path.unlink()
        except OSError:
            # Database deletion is authoritative; a missing file does not restore DB rows.
            pass


def delete_related_records(db, roots: list[tuple[str, str]]) -> list[tuple[Path, str]]:
    _counts, files = _walk_roots(db, roots, delete=True)
    return files


def remove_related_files(files: list[tuple[Path, str]]) -> None:
    _remove_files(files)


def company_deletion_roots(db, company_id: str) -> tuple[list[tuple[str, str]], list[str], str | None]:
    company = _root_row(db, "companies", company_id)
    if not company:
        return [], [], None
    employees = db.execute(
        text("SELECT id, user_id FROM patients WHERE company_id = :company_id"),
        {"company_id": company_id},
    ).mappings().all()
    owner_user_id = company.get("owner_user_id")
    roots = [("companies", company_id)]
    roots.extend(("users", str(row["user_id"])) for row in employees if row.get("user_id"))
    if owner_user_id:
        roots.append(("users", str(owner_user_id)))
    return roots, [str(row["id"]) for row in employees], str(owner_user_id) if owner_user_id else None


def user_deletion_roots(db, user_id: str) -> tuple[list[tuple[str, str]], list[str]]:
    user = _root_row(db, "users", user_id)
    if not user:
        return [], []
    company = db.execute(
        text("SELECT id FROM companies WHERE owner_user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().first()
    roots = [("users", user_id)]
    employees: list[str] = []
    if company:
        employee_rows = db.execute(
            text("SELECT id, user_id FROM patients WHERE company_id = :company_id"),
            {"company_id": company["id"]},
        ).mappings().all()
        employees = [str(row["user_id"]) for row in employee_rows if row.get("user_id")]
        roots.insert(0, ("companies", str(company["id"])))
        roots.extend(("users", employee_id) for employee_id in employees)
    return roots, employees
