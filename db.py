import json
import os
import time

DATA_FILE = "notified_deals.json"
EXPIRY_DAYS = 30


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_notified_keys(data_dir: str = ".") -> set[str]:
    path = os.path.join(data_dir, DATA_FILE)
    data = _load(path)
    now = time.time()
    cutoff = now - EXPIRY_DAYS * 86400
    return {k for k, ts in data.items() if ts > cutoff}


def mark_notified(keys: list[str], data_dir: str = ".") -> None:
    path = os.path.join(data_dir, DATA_FILE)
    data = _load(path)
    now = time.time()

    cutoff = now - EXPIRY_DAYS * 86400
    data = {k: ts for k, ts in data.items() if ts > cutoff}

    for key in keys:
        data[key] = now
    _save(path, data)
