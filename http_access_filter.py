"""Filters only routine successful Uvicorn access messages.

Application prints, provider debug messages, tracebacks, and unsuccessful HTTP
requests remain visible. This module deliberately does not configure logging:
both stdout and stderr are intercepted by Story Weaver's existing capture.
"""

import re

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_UVICORN_ACCESS = re.compile(
    r'^\s*INFO:\s+\S+\s+-\s+"[A-Z]+\s+[^"]+\s+HTTP/\d+(?:\.\d+)?"'
    r"\s+(?P<status>\d{3})(?:\s|$)"
)


def is_routine_access_log(line: str) -> bool:
    """Return True only for Uvicorn HTTP 2xx/3xx access records."""
    without_color = _ANSI_ESCAPE.sub("", line)
    match = _UVICORN_ACCESS.match(without_color)
    return bool(match and 200 <= int(match.group("status")) < 400)
