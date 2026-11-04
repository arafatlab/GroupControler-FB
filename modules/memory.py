import json
import re

from pathlib import Path

from config import DATA_DIR


class MemoryStore:

    MAX_HISTORY = 40

    def __init__(self):
        self.memory_dir = Path(DATA_DIR) / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, uid):
        uid = str(uid).strip()

        if not uid or not re.fullmatch(r"[A-Za-z0-9_-]+", uid):
            raise ValueError("Invalid user ID.")

        return self.memory_dir / f"{uid}.json"

    def _default_memory(self, uid):
        return {
            "uid": str(uid),
            "name": None,
            "loves_anu": False,
            "details": {},
            "history": []
        }

    def load(self, uid):
        path = self._get_path(uid)

        if not path.exists():
            return self._default_memory(uid)

        try:
            with path.open("r", encoding="utf-8") as file:
                memory = json.load(file)

            if not isinstance(memory, dict):
                raise ValueError("Invalid memory structure.")

            default = self._default_memory(uid)

            default.update(memory)

            if not isinstance(default.get("details"), dict):
                default["details"] = {}

            if not isinstance(default.get("history"), list):
                default["history"] = []

            return default

        except (json.JSONDecodeError, OSError, ValueError):
            print(f"[MEMORY] Could not load memory for user {uid}.")
            return self._default_memory(uid)

    def save(self, uid, memory):
        path = self._get_path(uid)

        if not isinstance(memory, dict):
            raise ValueError("Memory must be a dictionary.")

        memory["uid"] = str(uid)

        if not isinstance(memory.get("details"), dict):
            memory["details"] = {}

        if not isinstance(memory.get("history"), list):
            memory["history"] = []

        memory["history"] = memory["history"][-self.MAX_HISTORY:]

        temp_path = path.with_suffix(".tmp")

        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(
                memory,
                file,
                ensure_ascii=False,
                indent=4
            )

        temp_path.replace(path)

    def get_history(self, uid):
        memory = self.load(uid)
        return memory["history"]

    def add_exchange(self, uid, user_text, assistant_text):
        memory = self.load(uid)

        if not isinstance(user_text, str) or not isinstance(assistant_text, str):
            raise ValueError("Messages must be strings.")

        memory["history"].extend([
            {
                "role": "user",
                "content": user_text
            },
            {
                "role": "assistant",
                "content": assistant_text
            }
        ])

        memory["history"] = memory["history"][-self.MAX_HISTORY:]

        self.save(uid, memory)

    def update_name(self, uid, name):
        if not isinstance(name, str) or not name.strip():
            return

        memory = self.load(uid)
        memory["name"] = name.strip()[:100]

        self.save(uid, memory)

    def update_detail(self, uid, key, value):
        if not isinstance(key, str) or not key.strip():
            return

        memory = self.load(uid)

        memory["details"][key.strip()[:100]] = str(value)[:500]

        self.save(uid, memory)

    def set_loves_anu(self, uid, value=True):
        memory = self.load(uid)
        memory["loves_anu"] = bool(value)

        self.save(uid, memory)

    def clear_history(self, uid):
        memory = self.load(uid)
        memory["history"] = []

        self.save(uid, memory)
