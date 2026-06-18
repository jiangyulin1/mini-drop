"""Small JSON logger used by the Agent runtime."""

from __future__ import annotations

import json
import sys
import time
from typing import Any


def log_event(level: str, event: str, **fields: Any) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "level": level,
        "event": event,
        **fields,
    }
    print(json.dumps(record, ensure_ascii=False, default=str), file=sys.stderr if level == "error" else sys.stdout)
