#!/usr/bin/env python3
"""
Local dev server with HTTP Range support — required so that <video>
scrubbing actually works during local preview.

Background: Python's stdlib http.server only added Range support in 3.11.
On 3.9/3.10 the built-in server ignores Range headers and returns the
full file with HTTP 200, which makes HTML5 <video> elements feel
"un-draggable" because the browser can't seek to an un-buffered position.

Usage:
    python3 scripts/dev_server.py            # serves on http://localhost:8000
    python3 scripts/dev_server.py 8123       # serves on http://localhost:8123
"""

from __future__ import annotations

import os
import re
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that honors a single HTTP Range request."""

    def send_head(self):
        # Determine the file we'd be serving.
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        rng = self.headers.get("Range")
        if not rng:
            return super().send_head()

        m = _RANGE_RE.match(rng.strip())
        if not m:
            return super().send_head()

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            file_len = fs.st_size
            start_str, end_str = m.group(1), m.group(2)
            if start_str == "" and end_str == "":
                f.close()
                return super().send_head()
            if start_str == "":
                # Suffix: last N bytes
                length = int(end_str)
                if length <= 0:
                    f.close()
                    return super().send_head()
                start = max(file_len - length, 0)
                end = file_len - 1
            else:
                start = int(start_str)
                end = int(end_str) if end_str else file_len - 1
            if start >= file_len or end < start:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{file_len}")
                self.end_headers()
                f.close()
                return None
            end = min(end, file_len - 1)
            length = end - start + 1

            ctype = self.guess_type(path)
            self.send_response(HTTPStatus.PARTIAL_CONTENT)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_len}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()

            f.seek(start)
            # We override copyfile via a small wrapper; SimpleHTTPRequestHandler
            # closes the file after copyfile, which we replicate by returning
            # a tuple-like file object. Easiest: read and write here, return None
            # so the base class doesn't try to copy further.
            self._send_partial(f, length)
            f.close()
            return None
        except Exception:
            f.close()
            raise

    def _send_partial(self, f, length: int, chunk: int = 64 * 1024) -> None:
        remaining = length
        while remaining > 0:
            buf = f.read(min(chunk, remaining))
            if not buf:
                break
            try:
                self.wfile.write(buf)
            except (BrokenPipeError, ConnectionResetError):
                return
            remaining -= len(buf)

    def end_headers(self):
        # Encourage browsers not to cache during local development so that
        # a hard refresh always picks up your latest edits.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main(argv: list[str]) -> int:
    port = int(argv[1]) if len(argv) > 1 else 8000
    bind = "0.0.0.0"
    handler = partial(RangeHTTPRequestHandler, directory=os.getcwd())
    with ThreadingHTTPServer((bind, port), handler) as httpd:
        print(f"Serving HTTP on http://localhost:{port}/  (Range-enabled)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nshutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
