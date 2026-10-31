"""Local HTTP tests for skip, range-resume, and failed-download finalization."""
from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import subprocess
import sys

import requests

from apikah_crawler import config, crawl_static
from apikah_crawler.common import done, download_file, manifest_load


class Handler(BaseHTTPRequestHandler):
    payload = b"abcdefgh"
    status = 200
    last_range = None
    last_if_range = None
    range_history = []
    if_range_history = []
    request_count = 0
    delay_seconds = 0.0
    etag = '"v1"'
    last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
    omit_etag = False
    ignore_range = False
    range_start_delta = 0
    force_416_once = False
    request_lock = threading.Lock()

    def do_GET(self):
        with type(self).request_lock:
            type(self).request_count += 1
            type(self).last_range = self.headers.get("Range")
            type(self).last_if_range = self.headers.get("If-Range")
            type(self).range_history.append(type(self).last_range)
            type(self).if_range_history.append(type(self).last_if_range)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.status != 200:
            self.send_response(self.status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if type(self).force_416_once:
            type(self).force_416_once = False
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(self.payload)}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        start = 0
        partial = bool(self.last_range and not self.ignore_range)
        if partial:
            start = int(self.last_range.removeprefix("bytes=").split("-", 1)[0])
            start += self.range_start_delta
        body = self.payload[start:] if partial else self.payload
        self.send_response(206 if partial else 200)
        self.send_header("Content-Length", str(len(body)))
        if self.etag and not self.omit_etag:
            self.send_header("ETag", self.etag)
        self.send_header("Last-Modified", self.last_modified)
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{len(self.payload)-1}/{len(self.payload)}")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class DownloadFileTests(unittest.TestCase):
    def setUp(self):
        Handler.status = 200
        Handler.last_range = None
        Handler.last_if_range = None
        Handler.range_history = []
        Handler.if_range_history = []
        Handler.request_count = 0
        Handler.delay_seconds = 0.0
        Handler.etag = '"v1"'
        Handler.last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
        Handler.omit_etag = False
        Handler.ignore_range = False
        Handler.range_start_delta = 0
        Handler.force_416_once = False
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/sample"
        self.temp = TemporaryDirectory()
        self.old_metadata = config.METADATA
        config.METADATA = Path(self.temp.name) / "metadata"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        config.METADATA = self.old_metadata
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
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.last_range, "bytes=3-")
        self.assertEqual(Handler.last_if_range, Handler.etag)
        self.assertEqual(destination.read_bytes(), Handler.payload)
        self.assertFalse(part.exists())
        self.assertFalse(part.with_name(part.name + ".meta.json").exists())

    def test_partial_without_validator_is_restarted_not_appended(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(b"old")

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.range_history, [None])
        self.assertEqual(destination.read_bytes(), Handler.payload)

    def test_mismatched_content_range_restarts_from_zero(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload[:3])
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))
        Handler.range_start_delta = 1

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.range_history, ["bytes=3-", None])
        self.assertEqual(destination.read_bytes(), Handler.payload)

    def test_missing_resume_etag_restarts_instead_of_appending(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload[:3])
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))
        Handler.omit_etag = True

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.range_history, ["bytes=3-", None])
        self.assertEqual(destination.read_bytes(), Handler.payload)

    def test_changed_etag_200_response_replaces_old_partial(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload[:3])
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": '"old"', "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))
        Handler.etag = '"new"'
        Handler.payload = b"new representation"
        Handler.ignore_range = True

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.last_range, "bytes=3-")
        self.assertEqual(Handler.last_if_range, '"old"')
        self.assertEqual(destination.read_bytes(), Handler.payload)

    def test_416_with_incomplete_part_restarts_from_zero(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload[:3])
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))
        Handler.force_416_once = True

        result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(Handler.range_history, ["bytes=3-", None])
        self.assertEqual(destination.read_bytes(), Handler.payload)

    def test_complete_part_finalizes_without_request(self):
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(Handler.payload)
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))

        with patch("requests.get", side_effect=AssertionError("complete part should finalize locally")):
            result = download_file(self.url, destination)

        self.assertEqual(result, "ok")
        self.assertEqual(destination.read_bytes(), Handler.payload)
        self.assertEqual(Handler.request_count, 0)

    def test_http_failure_never_creates_a_successful_final_file(self):
        Handler.status = 503
        destination = Path(self.temp.name) / "sample.bin"
        part = destination.with_suffix(destination.suffix + ".part")
        part.write_bytes(b"partial")
        part.with_name(part.name + ".meta.json").write_text(json.dumps({
            "etag": Handler.etag, "last_modified": Handler.last_modified,
            "total_length": len(Handler.payload),
        }))

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

    def test_two_processes_share_one_destination_download(self):
        Handler.payload = b"x" * 1_000_000
        Handler.delay_seconds = 0.25
        destination = Path(self.temp.name) / "shared.bin"
        metadata = Path(self.temp.name) / "metadata"
        package_parent = Path(config.__file__).resolve().parents[1]
        script = (
            "import sys; from pathlib import Path; "
            f"sys.path.insert(0, {str(package_parent)!r}); "
            "from apikah_crawler import config; config.METADATA = Path(sys.argv[3]); "
            "from apikah_crawler.common import download_file; "
            "print(download_file(sys.argv[1], Path(sys.argv[2])))"
        )
        commands = [[sys.executable, "-c", script, self.url, str(destination), str(metadata)]
                    for _ in range(2)]
        processes = [subprocess.Popen(cmd, cwd=self.temp.name, text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for cmd in commands]
        results = [process.communicate(timeout=30) for process in processes]

        self.assertEqual([process.returncode for process in processes], [0, 0], results)
        self.assertCountEqual([out.strip() for out, _err in results], ["ok", "skipped"])
        self.assertEqual(Handler.request_count, 1)
        self.assertEqual(destination.read_bytes(), Handler.payload)
        lock_files = list((metadata / "locks").glob("*.lock"))
        self.assertEqual(len(lock_files), 1, "target locks should be centralized under metadata/locks")
        self.assertFalse(destination.with_name(destination.name + ".lock").exists())


if __name__ == "__main__":
    unittest.main()
