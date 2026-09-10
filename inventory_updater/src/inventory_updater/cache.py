from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from marcone.models import PartPricing


class PriceCache:
    """SQLite-backed cache for Marcone part lookups."""

    def __init__(self, db_path: str = ".cache/marcone_prices.sqlite") -> None:
        self.db_path = db_path
        self._write_lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        return sqlite3.connect(self.db_path, timeout=30.0)

    def _init_db(self) -> None:
        with self._write_lock, self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS part_cache (
                    part_number TEXT PRIMARY KEY,
                    make TEXT,
                    customer_cost REAL,
                    list_price REAL,
                    core_charge REAL,
                    in_stock INTEGER,
                    description TEXT,
                    metadata TEXT,
                    status TEXT,
                    updated_at TIMESTAMP
                )
                """
            )
            conn.commit()

    def get(
        self, part_number: str, max_age_seconds: float | None = None
    ) -> PartPricing | None:
        """Retrieve cached pricing if present and not expired."""
        clean_part = part_number.strip().upper()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT make, customer_cost, list_price, core_charge, in_stock, description, metadata, status, updated_at
                FROM part_cache
                WHERE part_number = ?
                """,
                (clean_part,),
            )
            row = cur.fetchone()

        if not row:
            return None

        (
            make,
            customer_cost,
            list_price,
            core_charge,
            in_stock,
            description,
            metadata_json,
            status,
            updated_at_str,
        ) = row

        if status != "ok":
            return None

        if max_age_seconds is not None and updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                age = (datetime.now(timezone.utc) - updated_at).total_seconds()
                if age > max_age_seconds:
                    return None
            except ValueError:
                return None

        metadata: dict[str, Any] = {}
        if metadata_json:
            try:
                metadata = json.loads(metadata_json)
            except ValueError:
                pass

        return PartPricing(
            part_number=clean_part,
            make=make or "",
            description=description,
            customer_cost=customer_cost,
            list_price=list_price,
            core_charge=core_charge,
            in_stock=bool(in_stock) if in_stock is not None else None,
            metadata=metadata,
        )

    def get_many(
        self, part_numbers: list[str], max_age_seconds: float | None = None
    ) -> tuple[dict[str, PartPricing], set[str]]:
        """Batch retrieve cached pricing and known missing parts.

        Returns (cached_map, missing_set), where cached_map maps uppercase part numbers
        to valid unexpired PartPricing, and missing_set contains uppercase part numbers
        marked not_found within TTL.
        """
        clean_parts = list(
            dict.fromkeys(p.strip().upper() for p in part_numbers if p and str(p).strip())
        )
        if not clean_parts:
            return {}, set()

        cached_map: dict[str, PartPricing] = {}
        missing_set: set[str] = set()
        now = datetime.now(timezone.utc)
        chunk_size = 500

        with self._get_connection() as conn:
            cur = conn.cursor()
            for i in range(0, len(clean_parts), chunk_size):
                chunk = clean_parts[i : i + chunk_size]
                placeholders = ",".join("?" for _ in chunk)
                cur.execute(
                    f"""
                    SELECT part_number, make, customer_cost, list_price, core_charge,
                           in_stock, description, metadata, status, updated_at
                    FROM part_cache
                    WHERE part_number IN ({placeholders})
                    """,
                    chunk,
                )
                rows = cur.fetchall()
                for row in rows:
                    (
                        part_no,
                        make,
                        customer_cost,
                        list_price,
                        core_charge,
                        in_stock,
                        description,
                        metadata_json,
                        status,
                        updated_at_str,
                    ) = row

                    if max_age_seconds is not None and updated_at_str:
                        try:
                            updated_at = datetime.fromisoformat(updated_at_str)
                            if (now - updated_at).total_seconds() > max_age_seconds:
                                continue
                        except ValueError:
                            continue

                    if status == "ok":
                        metadata: dict[str, Any] = {}
                        if metadata_json:
                            try:
                                metadata = json.loads(metadata_json)
                            except ValueError:
                                pass
                        cached_map[part_no] = PartPricing(
                            part_number=part_no,
                            make=make or "",
                            description=description,
                            customer_cost=customer_cost,
                            list_price=list_price,
                            core_charge=core_charge,
                            in_stock=bool(in_stock) if in_stock is not None else None,
                            metadata=metadata,
                        )
                    elif status == "not_found":
                        missing_set.add(part_no)

        return cached_map, missing_set

    def set(self, pricing: PartPricing, status: str = "ok") -> None:
        """Cache pricing for a part."""
        clean_part = pricing.part_number.strip().upper()
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(pricing.metadata) if pricing.metadata else ""

        with self._write_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO part_cache (
                    part_number, make, customer_cost, list_price, core_charge,
                    in_stock, description, metadata, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(part_number) DO UPDATE SET
                    make = excluded.make,
                    customer_cost = excluded.customer_cost,
                    list_price = excluded.list_price,
                    core_charge = excluded.core_charge,
                    in_stock = excluded.in_stock,
                    description = excluded.description,
                    metadata = excluded.metadata,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    clean_part,
                    pricing.make,
                    pricing.customer_cost,
                    pricing.list_price,
                    pricing.core_charge,
                    int(pricing.in_stock) if pricing.in_stock is not None else None,
                    pricing.description,
                    metadata_json,
                    status,
                    now,
                ),
            )
            conn.commit()

    def set_not_found(self, part_number: str) -> None:
        """Record that a part was not found to prevent redundant lookups."""
        clean_part = part_number.strip().upper()
        now = datetime.now(timezone.utc).isoformat()
        with self._write_lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO part_cache (part_number, status, updated_at)
                VALUES (?, 'not_found', ?)
                ON CONFLICT(part_number) DO UPDATE SET
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (clean_part, now),
            )
            conn.commit()

    def is_known_missing(
        self, part_number: str, max_age_seconds: float | None = None
    ) -> bool:
        """Check if part was previously marked not found."""
        clean_part = part_number.strip().upper()
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, updated_at FROM part_cache WHERE part_number = ?",
                (clean_part,),
            )
            row = cur.fetchone()

        if not row:
            return False

        status, updated_at_str = row
        if status != "not_found":
            return False

        if max_age_seconds is not None and updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                age = (datetime.now(timezone.utc) - updated_at).total_seconds()
                if age > max_age_seconds:
                    return False
            except ValueError:
                return False

        return True
