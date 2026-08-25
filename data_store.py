"""Registro acquisti condiviso (persistenza).

Astrazione minimale sul registro degli acquisti della lega: e' l'unico dato
"scrivibile" dell'applicazione (Listone/Moduli/Squadre restano di sola lettura).

Backend predefinito: SQLite su file locale. L'interfaccia `PurchaseStore` permette
di sostituirlo in futuro con Google Sheets o Postgres senza toccare la UI.

NB: su Streamlit Community Cloud il filesystem e' effimero (si azzera ai redeploy
e agli stop). Per un'asta condivisa realmente persistente usare un backend esterno
(Google Sheets / Supabase) implementando la stessa interfaccia.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class Purchase:
    id: int
    nome: str
    squadra: str
    costo: float


class PurchaseStore(Protocol):
    def list_purchases(self) -> list[Purchase]: ...
    def add_purchase(self, nome: str, squadra: str, costo: float) -> Purchase: ...
    def remove_purchase(self, purchase_id: int) -> None: ...
    def exists(self, nome: str) -> bool: ...
    def clear(self) -> None: ...
    def get_team_names(self) -> dict[str, str]: ...
    def set_team_name(self, orig: str, custom: str) -> None: ...
    def clear_team_names(self) -> None: ...


class SQLitePurchaseStore:
    """Registro acquisti su SQLite. Thread-safe per l'uso da Streamlit."""

    def __init__(self, path: str = "acquisti.db") -> None:
        self._path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS acquisti (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                nome    TEXT    NOT NULL,
                squadra TEXT    NOT NULL,
                costo   REAL    NOT NULL,
                nome_key TEXT   NOT NULL UNIQUE
            )
            """
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS team_names ("
            "orig TEXT PRIMARY KEY, custom TEXT NOT NULL)"
        )
        self._conn.commit()

    @staticmethod
    def _key(nome: str) -> str:
        return nome.strip().casefold()

    def list_purchases(self) -> list[Purchase]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, nome, squadra, costo FROM acquisti ORDER BY id"
            ).fetchall()
        return [Purchase(r["id"], r["nome"], r["squadra"], r["costo"]) for r in rows]

    def exists(self, nome: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM acquisti WHERE nome_key = ?", (self._key(nome),)
            ).fetchone()
        return row is not None

    def add_purchase(self, nome: str, squadra: str, costo: float) -> Purchase:
        nome = nome.strip()
        squadra = squadra.strip()
        key = self._key(nome)
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO acquisti (nome, squadra, costo, nome_key) VALUES (?, ?, ?, ?)",
                (nome, squadra, float(costo), key),
            )
            self._conn.commit()
            new_id = cur.lastrowid
        return Purchase(int(new_id), nome, squadra, float(costo))

    def remove_purchase(self, purchase_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM acquisti WHERE id = ?", (purchase_id,))
            self._conn.commit()

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM acquisti")
            self._conn.commit()

    # -- nomi squadre (override persistente) ---------------------------
    def get_team_names(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT orig, custom FROM team_names").fetchall()
        return {r["orig"]: r["custom"] for r in rows}

    def set_team_name(self, orig: str, custom: str) -> None:
        orig = orig.strip()
        custom = custom.strip()
        with self._lock:
            self._conn.execute(
                "INSERT INTO team_names (orig, custom) VALUES (?, ?) "
                "ON CONFLICT(orig) DO UPDATE SET custom = excluded.custom",
                (orig, custom),
            )
            self._conn.commit()

    def clear_team_names(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM team_names")
            self._conn.commit()


# ----------------------------------------------------------------------------
# Validazione (porting di SvuotaInserimento)
# ----------------------------------------------------------------------------
class ValidationError(Exception):
    pass


def validate_and_add(
    store: PurchaseStore,
    ref,
    nome: str,
    squadra: str,
    costo,
) -> Purchase:
    """Valida un acquisto come la macro VBA e lo registra.

    Regole: nome presente nel listone, non gia' registrato, squadra valida, costo numerico >= 0.
    `ref` e' un ReferenceData (usa canonical_name e teams).
    """
    nome = (nome or "").strip()
    squadra = (squadra or "").strip()

    if not nome:
        raise ValidationError("Inserisci il nome del giocatore.")

    canonical = ref.canonical_name(nome)
    if canonical is None:
        raise ValidationError(f'"{nome}" non e\' presente nel listone.')

    if squadra not in ref.teams:
        raise ValidationError(f'Squadra "{squadra}" non riconosciuta.')

    try:
        costo_val = float(costo)
    except (TypeError, ValueError):
        raise ValidationError("Il costo deve essere un numero.")
    if costo_val < 0:
        raise ValidationError("Il costo non puo' essere negativo.")

    if store.exists(canonical):
        raise ValidationError(f'"{canonical}" e\' gia\' stato registrato.')

    return store.add_purchase(canonical, squadra, costo_val)
