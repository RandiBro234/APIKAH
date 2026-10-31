"""Local HTTP tests for skip, range-resume, and failed-download finalization."""
from __future__ import annotations

import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import requests

from apikah_crawler import config, crawl_static
from apikah_crawler.common import done, download_file, manifest_load


class Handler(BaseHTTPRequestHandler):
    payload = b"abcdefgh"
    status = 200
    last_range = None

    def do_GET(self):
        type(self).last_range = self.headers.get("Range")
        if self.status != 200:
            self.send_response(self.status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        start = 0
        if self.last_range:
            start = int(self.last_range.removeprefix("bytes=").split("-", 1)[0])
        body = self.payload[start:]
        self.send_response(206 if self.last_range else 200)
        self.send_header("Content-Length", str(len(body)))
        if self.last_range:
            self.send_header("Content-Range", f"bytes {start}-{len(self.payload)-1}/{len(self.payload)}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class DownloadFileTests(unittest.TestCase):
    def setUp(self):
        Handler.status = 200
        Handler.last_range = None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/sample"
        self.temp = TemporaryDirectory()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_existing_complete_file_is_skipped_without_request(self):
        destination = Path(self.temp.name) / "sample.bin"
        destination.write_bytes(b"already complete")

        with patch("requests.get", side_effect=AssertionError("must skip")):
            result = download_file(self.url, destination)

        self.assertEqual(result, "skipped")
        self.assertEqual(destination.read_bytes(), b"already complete")

    def test_partial_file_resumes_and_atomically_finalizes(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload[:3])

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.last_range, "bytes=3-")
        self.assertEqual(destination.read_bytes(), Handler.payload)
        self.assertFalse(part.exists())

    def test_http_failure_never_creates_a_successful_final_file(self):
        Handler.status = 503
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(b"partial")

        with self.assertRaises(requests.HTTPError):
            download_file(self.url, destination)

        self.assertFalse(destination.exists())
        self.assertFalse(done(destination))
        self.assertEqual(part.read_bytes(), b"partial")

    def test_crawler_marks_http_failure_failed_not_ok(self):
        Handler.status = 503
        destination = Path(self.temp.name) / "sample.bin"
        previous_metadata = config.METADATA
        config.METADATA = Path(self.temp.name) / "metadata"
        try:
            with patch.object(crawl_static, "with_retry", side_effect=lambda fn, *a, **kw: fn(*a, **kw)), \
                 patch.object(crawl_static.time, "sleep"):
                crawl_static.fetch("test", self.url, destination, dry=False)
            record = manifest_load("static")["test/sample.bin"]
        finally:
            config.METADATA = previous_metadata

        self.assertEqual(record["status"], "failed")
        self.assertFalse(destination.exists())

    def test_not_found_is_recorded_without_creating_destination(self):
        Handler.status = 404
        destination = Path(self.temp.name) / "sample.bin"

        result = download_file(self.url, destination)

        self.assertEqual(result, "missing")
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
