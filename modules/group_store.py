import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR


DB_FILE = Path(DATA_DIR) / "group_control.db"


class GroupStore:
    def __init__(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        db = sqlite3.connect(DB_FILE, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    target_id TEXT,
                    message TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_reminders_due
                ON reminders(delivered, remind_at);

                CREATE TABLE IF NOT EXISTS group_rules (
                    thread_id TEXT PRIMARY KEY,
                    rules TEXT NOT NULL,
                    updated_by TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    reporter_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS group_members (
    thread_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT,
    profile_url TEXT,
    avatar_url TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_present INTEGER NOT NULL DEFAULT 1,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_name
ON group_members(thread_id, name);

CREATE INDEX IF NOT EXISTS idx_group_members_present
ON group_members(thread_id, is_present);

CREATE TABLE IF NOT EXISTS group_sync_state (
    thread_id TEXT PRIMARY KEY,
    last_synced TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onboarding_sent (
                    thread_id TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY(thread_id, admin_id)
                );
            """)


    # GROUP MEMBER DATABASE

    def sync_members(self, thread_id, members, admin_ids=None):
        """Save a complete member snapshot and detect membership/admin changes."""
        if not isinstance(members, (list, tuple)) or not members:
            raise ValueError("Empty or invalid member snapshot; refusing to overwrite.")

        normalized = {}
        for item in members:
            if not isinstance(item, dict):
                raise ValueError("Invalid member record.")

            user_id = str(item.get("id") or item.get("user_id") or "").strip()
            if not user_id:
                raise ValueError("Member record is missing Facebook ID.")

            normalized[user_id] = {
                "name": str(item.get("name") or "").strip(),
                "profile_url": item.get("profile_url"),
                "avatar_url": item.get("avatar_url"),
            }

        tid = str(thread_id)
        now = self.now()
        admin_set = (
            {str(value) for value in admin_ids if value}
            if admin_ids is not None else None
        )

        changes = {
            "joined": [],
            "left": [],
            "promoted": [],
            "demoted": [],
        }

        with self.connect() as db:
            old_rows = db.execute(
                "SELECT * FROM group_members WHERE thread_id = ? AND is_present = 1",
                (tid,),
            ).fetchall()
            old = {row["user_id"]: dict(row) for row in old_rows}

            for user_id, member in normalized.items():
                previous = old.get(user_id)

                if admin_set is None:
                    is_admin = (
                        int(previous["is_admin"])
                        if previous else 0
                    )
                else:
                    is_admin = int(user_id in admin_set)

                db.execute("""
                    INSERT INTO group_members (
                        thread_id, user_id, name, profile_url, avatar_url,
                        is_admin, is_present, first_seen, last_seen
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(thread_id, user_id) DO UPDATE SET
                        name = excluded.name,
                        profile_url = excluded.profile_url,
                        avatar_url = excluded.avatar_url,
                        is_admin = excluded.is_admin,
                        is_present = 1,
                        last_seen = excluded.last_seen
                """, (
                    tid, user_id, member["name"],
                    member["profile_url"], member["avatar_url"],
                    is_admin, now, now,
                ))

                current = {
                    "user_id": user_id,
                    "name": member["name"],
                    "is_admin": bool(is_admin),
                }

                if previous is None:
                    changes["joined"].append(current)
                elif admin_set is not None:
                    was_admin = bool(previous["is_admin"])
                    if not was_admin and is_admin:
                        changes["promoted"].append(current)
                    elif was_admin and not is_admin:
                        changes["demoted"].append(current)

            missing_ids = set(old) - set(normalized)
            for user_id in missing_ids:
                previous = old[user_id]
                db.execute("""
                    UPDATE group_members
                    SET is_present = 0, last_seen = ?
                    WHERE thread_id = ? AND user_id = ?
                """, (now, tid, user_id))
                changes["left"].append({
                    "user_id": user_id,
                    "name": previous["name"],
                    "is_admin": bool(previous["is_admin"]),
                })

            db.execute("""
                INSERT INTO group_sync_state (thread_id, last_synced)
                VALUES (?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    last_synced = excluded.last_synced
            """, (tid, now))

        return changes

    def list_members(self, thread_id, include_absent=False):
        with self.connect() as db:
            query = "SELECT * FROM group_members WHERE thread_id = ?"
            if not include_absent:
                query += " AND is_present = 1"
            query += " ORDER BY name COLLATE NOCASE"
            rows = db.execute(query, (str(thread_id),)).fetchall()
            return [dict(row) for row in rows]

    def resolve_member(self, thread_id, query):
        """Resolve an exact Facebook ID or unique exact display name."""
        value = str(query or "").strip()
        if not value:
            return {"status": "not_found", "member": None, "matches": []}

        members = self.list_members(thread_id)

        for member in members:
            if member["user_id"] == value:
                return {"status": "ok", "member": member, "matches": [member]}

        matches = [
            member for member in members
            if (member.get("name") or "").strip().casefold() == value.casefold()
        ]

        if len(matches) == 1:
            return {"status": "ok", "member": matches[0], "matches": matches}

        if len(matches) > 1:
            return {"status": "ambiguous", "member": None, "matches": matches}

        return {"status": "not_found", "member": None, "matches": []}

    def mark_member_left(self, thread_id, user_id):
        with self.connect() as db:
            cursor = db.execute("""
                UPDATE group_members
                SET is_present = 0, last_seen = ?
                WHERE thread_id = ? AND user_id = ? AND is_present = 1
            """, (self.now(), str(thread_id), str(user_id)))
            return cursor.rowcount > 0

    # REMINDERS

    def add_reminder(
        self, thread_id, creator_id, message, remind_at, target_id=None
    ):
        with self.connect() as db:
            cursor = db.execute("""
                INSERT INTO reminders
                (thread_id, creator_id, target_id, message, remind_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(thread_id), str(creator_id),
                str(target_id) if target_id else None,
                str(message), str(remind_at), self.now()
            ))
            return cursor.lastrowid

    def list_reminders(self, thread_id):
        with self.connect() as db:
            rows = db.execute("""
                SELECT * FROM reminders
                WHERE thread_id = ? AND delivered = 0
                ORDER BY remind_at
            """, (str(thread_id),)).fetchall()
            return [dict(row) for row in rows]

    def cancel_reminder(self, reminder_id, thread_id, requester_id, is_admin=False):
        with self.connect() as db:
            row = db.execute("""
                SELECT creator_id FROM reminders
                WHERE id = ? AND thread_id = ? AND delivered = 0
            """, (int(reminder_id), str(thread_id))).fetchone()

            if row is None:
                return False

            if str(row["creator_id"]) != str(requester_id) and not is_admin:
                return False

            db.execute("""
                DELETE FROM reminders
                WHERE id = ? AND thread_id = ?
            """, (int(reminder_id), str(thread_id)))
            return True

    def get_due_reminders(self):
        with self.connect() as db:
            rows = db.execute("""
                SELECT * FROM reminders
                WHERE delivered = 0 AND remind_at <= ?
                ORDER BY remind_at
            """, (self.now(),)).fetchall()
            return [dict(row) for row in rows]

    def mark_reminder_delivered(self, reminder_id):
        with self.connect() as db:
            db.execute("""
                UPDATE reminders SET delivered = 1 WHERE id = ?
            """, (int(reminder_id),))

    # GROUP RULES

    def set_rules(self, thread_id, rules, admin_id):
        with self.connect() as db:
            db.execute("""
                INSERT INTO group_rules
                (thread_id, rules, updated_by, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    rules = excluded.rules,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
            """, (str(thread_id), str(rules), str(admin_id), self.now()))

    def get_rules(self, thread_id):
        with self.connect() as db:
            row = db.execute("""
                SELECT rules FROM group_rules WHERE thread_id = ?
            """, (str(thread_id),)).fetchone()
            return row["rules"] if row else None

    def remove_rules(self, thread_id):
        with self.connect() as db:
            cursor = db.execute("""
                DELETE FROM group_rules WHERE thread_id = ?
            """, (str(thread_id),))
            return cursor.rowcount > 0

    # WARNINGS

    def add_warning(self, thread_id, user_id, admin_id, reason):
        with self.connect() as db:
            cursor = db.execute("""
                INSERT INTO warnings
                (thread_id, user_id, admin_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(thread_id), str(user_id),
                str(admin_id), str(reason), self.now()
            ))
            return cursor.lastrowid

    def get_warnings(self, thread_id, user_id=None):
        with self.connect() as db:
            if user_id is None:
                rows = db.execute("""
                    SELECT * FROM warnings
                    WHERE thread_id = ?
                    ORDER BY id DESC
                """, (str(thread_id),)).fetchall()
            else:
                rows = db.execute("""
                    SELECT * FROM warnings
                    WHERE thread_id = ? AND user_id = ?
                    ORDER BY id DESC
                """, (str(thread_id), str(user_id))).fetchall()

            return [dict(row) for row in rows]

    # REPORTS

    def add_report(self, thread_id, reporter_id, target_id, reason):
        with self.connect() as db:
            cursor = db.execute("""
                INSERT INTO reports
                (thread_id, reporter_id, target_id, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(thread_id), str(reporter_id),
                str(target_id), str(reason), self.now()
            ))
            return cursor.lastrowid

    # ADMIN ONBOARDING

    def onboarding_was_sent(self, thread_id, admin_id):
        with self.connect() as db:
            row = db.execute("""
                SELECT 1 FROM onboarding_sent
                WHERE thread_id = ? AND admin_id = ?
            """, (str(thread_id), str(admin_id))).fetchone()
            return row is not None

    def mark_onboarding_sent(self, thread_id, admin_id):
        with self.connect() as db:
            db.execute("""
                INSERT OR IGNORE INTO onboarding_sent
                (thread_id, admin_id, sent_at)
                VALUES (?, ?, ?)
            """, (str(thread_id), str(admin_id), self.now()))
