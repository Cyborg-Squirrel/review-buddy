"""Shared utilities for API classes."""
import requests


def stream_file_lines(
    url: str, headers: dict, params: dict, start_line: int, end_line: int
) -> list[str]:
    """Streams a URL and returns lines in [start_line, end_line], 1-indexed."""
    lines = []
    with requests.get(url, headers=headers, params=params, stream=True, timeout=30) as response:
        response.raise_for_status()
        for i, line in enumerate(response.iter_lines(decode_unicode=True), start=1):
            if i >= start_line:
                lines.append(line)
            if i >= end_line:
                break
    return lines
