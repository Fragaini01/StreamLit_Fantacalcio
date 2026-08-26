from pathlib import Path

p = Path("data_store.py")
src = p.read_text(encoding="utf-8")


def rep(old, new, label):
    global src
    assert src.count(old) == 1, (label, src.count(old))
    src = src.replace(old, new)
    print("OK", label)


# import hashlib
rep(
    "import sqlite3\nimport threading\n",
    "import hashlib\nimport sqlite3\nimport threading\n",
    "import hashlib",
)

# _hash_password helper (dopo gli import/typing, prima di @dataclass Purchase)
rep(
    "from typing import Optional, Protocol\n",
    "from typing import Optional, Protocol\n\n\n_PWD_SALT = \"fantamantra-2026\"\n\n\n"
    "def _hash_password(password: str) -> str:\n"
    "    return hashlib.sha256((_PWD_SALT + (password or \"\")).encode()).hexdigest()\n",
    "_hash_password",
)

# Protocol: aggiungi metodi auth
rep(
    "    def get_notes(self, owner: str) -> dict[str, str]: ...\n"
    "    def set_note(self, owner: str, nome: str, nota: str) -> None: ...\n",
    "    def get_notes(self, owner: str) -> dict[str, str]: ...\n"
    "    def set_note(self, owner: str, nome: str, nota: str) -> None: ...\n"
    "    def get_password_hash(self, player: str) -> Optional[str]: ...\n"
    "    def set_password(self, player: str, password: str) -> None: ...\n"
    "    def verify_password(self, player: str, password: str) -> bool: ...\n"
    "    def clear_passwords(self) -> None: ...\n",
    "protocol auth",
)

# Tabella player_auth
rep(
    "        self._conn.execute(\n"
    "            \"CREATE TABLE IF NOT EXISTS notes (\"\n"
    "            \"owner TEXT NOT NULL, nome TEXT NOT NULL, nota TEXT NOT NULL, \"\n"
    "            \"PRIMARY KEY (owner, nome))\"\n"
    "        )\n"
    "        self._conn.commit()\n",
    "        self._conn.execute(\n"
    "            \"CREATE TABLE IF NOT EXISTS notes (\"\n"
    "            \"owner TEXT NOT NULL, nome TEXT NOT NULL, nota TEXT NOT NULL, \"\n"
    "            \"PRIMARY KEY (owner, nome))\"\n"
    "        )\n"
    "        self._conn.execute(\n"
    "            \"CREATE TABLE IF NOT EXISTS player_auth (\"\n"
    "            \"player TEXT PRIMARY KEY, pwd_hash TEXT NOT NULL)\"\n"
    "        )\n"
    "        self._conn.commit()\n",
    "table player_auth",
)

# Metodi auth (dopo set_note)
rep(
    "                self._conn.commit()\n\n\n"
    "# ----------------------------------------------------------------------------\n"
    "# Validazione (porting di SvuotaInserimento)\n",
    "                self._conn.commit()\n\n"
    "    # -- autenticazione giocatori --------------------------------------\n"
    "    def get_password_hash(self, player: str) -> Optional[str]:\n"
    "        with self._lock:\n"
    "            row = self._conn.execute(\n"
    "                \"SELECT pwd_hash FROM player_auth WHERE player = ?\", (player.strip(),)\n"
    "            ).fetchone()\n"
    "        return row[\"pwd_hash\"] if row else None\n\n"
    "    def set_password(self, player: str, password: str) -> None:\n"
    "        with self._lock:\n"
    "            self._conn.execute(\n"
    "                \"INSERT INTO player_auth (player, pwd_hash) VALUES (?, ?) \"\n"
    "                \"ON CONFLICT(player) DO UPDATE SET pwd_hash = excluded.pwd_hash\",\n"
    "                (player.strip(), _hash_password(password)),\n"
    "            )\n"
    "            self._conn.commit()\n\n"
    "    def verify_password(self, player: str, password: str) -> bool:\n"
    "        stored = self.get_password_hash(player)\n"
    "        return stored is not None and stored == _hash_password(password)\n\n"
    "    def clear_passwords(self) -> None:\n"
    "        with self._lock:\n"
    "            self._conn.execute(\"DELETE FROM player_auth\")\n"
    "            self._conn.commit()\n\n\n"
    "# ----------------------------------------------------------------------------\n"
    "# Validazione (porting di SvuotaInserimento)\n",
    "auth methods",
)

p.write_text(src, encoding="utf-8")
print("DONE")
