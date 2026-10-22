#!/usr/bin/env python3
# License: Apache-2.0; scope and full text: ../../LICENSING.md
"""Unit tests for harnessrouter.py with mocked HTTP and SSE. Run: python3 -m unittest templates/python/test_harnessrouter.py"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnessrouter as hrm  # noqa: E402

SID, RID = "hsess0001", "resp_0001"
FILES = [
    {"object": "file", "id": "cfile_a", "file_id": "cfile_a", "container_id": SID, "filename": "index.html", "path": "site/index.html",
     "bytes": 40, "media_type": "text/html", "download_url": f"https://api.harnessrouter.ai/v1/containers/{SID}/files/cfile_a/content"},
    {"object": "file", "id": "cfile_b", "file_id": "cfile_b", "container_id": SID, "filename": "style.css", "path": "site/style.css",
     "bytes": 20, "media_type": "text/css", "download_url": f"https://api.harnessrouter.ai/v1/containers/{SID}/files/cfile_b/content"},
]
FINAL = {"id": RID, "object": "response", "status": "completed", "metadata": {"session_id": SID}, "output": [
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Working on it.", "annotations": []}]},
    {"type": "function_call", "name": "write", "arguments": "{}", "call_id": "call_1", "status": "completed"},
    {"type": "function_call_output", "call_id": "call_1", "output": "ok"},
    {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Made two files.", "annotations": [
        {"type": "container_file_citation", "container_id": SID, "file_id": "cfile_a", "filename": "site/index.html",
         "download_url": FILES[0]["download_url"], "start_index": 0, "end_index": 9}]}]},
]}
CREATED = {"id": RID, "object": "response", "status": "in_progress", "output": [], "metadata": {"session_id": SID}}


def frames(evs):
    return "".join(f"data: {json.dumps(e)}\n\n" for e in evs).encode()


STREAM = frames([
    {"type": "response.created", "sequence_number": 0, "response": CREATED},
    {"type": "response.in_progress", "sequence_number": 1, "response": CREATED},
    {"type": "response.output_item.added", "item": {"type": "function_call", "name": "Write", "arguments": ""}},
    {"type": "response.output_text.delta", "delta": "Made two files."},
    {"type": "response.completed", "response": FINAL},
])


class FakeResponse(io.BytesIO):
    def __init__(self, body=b"", headers=None, status=200):
        super().__init__(body if isinstance(body, bytes) else json.dumps(body).encode())
        self.headers = {**{"Content-Type": "application/json"}, **(headers or {})}
        self.status = status


class Router:
    """A fake opener: route(req) -> FakeResponse, or raises HTTPError for (status, body)."""

    def __init__(self, route):
        self.route, self.calls = route, []

    def __call__(self, req, timeout):
        body = json.loads(req.data) if req.data else None
        call = {"url": req.full_url, "method": req.get_method(), "headers": {k.lower(): v for k, v in req.header_items()}, "body": body}
        self.calls.append(call)
        out = self.route(call)
        if isinstance(out, tuple):
            status, payload, hdrs = (out + ({},))[:3]
            raise urllib.error.HTTPError(req.full_url, status, "err", hdrs, io.BytesIO(json.dumps(payload).encode()))
        return out


def client(route):
    r = Router(route)
    return hrm.HarnessRouter(api_key="sk-hr-testtesttest", opener=r, sleep=lambda s: None), r


class ParseTest(unittest.TestCase):
    def test_parse_sse_handles_crlf_comments_done_junk_multiline_and_tail(self):
        text = (b": keepalive\r\n\r\n" + STREAM.replace(b"\n", b"\r\n") + b"data: [DONE]\n\ndata: not json\n\n"
                b'data: {"type":\ndata: "x.multi"}\n\nevent: ignored\ndata: {"type":"x.tail"}')
        lines = io.BytesIO(text).readlines()
        types = [e["type"] for e in hrm.parse_sse(lines)]
        self.assertEqual(types, ["response.created", "response.in_progress", "response.output_item.added",
                                 "response.output_text.delta", "response.completed", "x.multi", "x.tail"])

    def test_answer_and_files(self):
        self.assertEqual(hrm.answer_text(FINAL), "Made two files.")
        self.assertEqual([a["filename"] for a in hrm.produced_files(FINAL)], ["site/index.html"])

    def test_progress_is_plain(self):
        self.assertEqual(hrm.to_progress({"type": "response.output_text.delta", "delta": "hi"}), {"kind": "text", "delta": "hi"})
        self.assertEqual(hrm.to_progress({"type": "response.output_item.added", "item": {"type": "function_call", "name": "Bash"}}),
                         {"kind": "activity", "label": "Running a step"})
        self.assertEqual(hrm.to_progress({"type": "response.failed", "response": {"status": "cancelled"}}), {"kind": "done", "status": "cancelled"})
        self.assertIsNone(hrm.to_progress({"type": "response.content_part.added"}))


class ClientTest(unittest.TestCase):
    def test_run_streamed_request_and_ids_at_created(self):
        hr, r = client(lambda c: FakeResponse(STREAM, {"Content-Type": "text/event-stream"}))
        order = []
        out = hr.run_streamed("chrn_1", "hello", previous_response_id="resp_0", session_id=SID, idempotency_key="k-1",
                              on_ids=lambda rid, sid: order.append(f"ids:{rid}:{sid}"), on_event=lambda e: order.append(e["type"]))
        self.assertEqual(out["status"], "completed")
        self.assertEqual(order[0], f"ids:{RID}:{SID}")
        c = r.calls[0]
        self.assertEqual((c["method"], c["url"]), ("POST", "https://api.harnessrouter.ai/v1/responses"))
        self.assertEqual(c["headers"]["authorization"], "Bearer sk-hr-testtesttest")
        self.assertEqual(c["headers"]["uhp-version"], "2026-09-28")
        self.assertEqual(c["headers"]["idempotency-key"], "k-1")
        self.assertEqual(c["headers"]["accept"], "text/event-stream")
        self.assertEqual(c["body"], {"input": "hello", "metadata": {"harness_id": "chrn_1", "session_id": SID},
                                     "previous_response_id": "resp_0", "stream": True})

    def test_stream_without_terminal_is_polled_not_resent(self):
        partial = frames([{"type": "response.created", "response": CREATED}, {"type": "response.output_text.delta", "delta": "x"}])
        polls = []

        def route(c):
            if c["method"] == "POST":
                return FakeResponse(partial)
            polls.append(1)
            return FakeResponse(CREATED if len(polls) < 3 else FINAL)
        hr, r = client(route)
        self.assertEqual(hr.run_streamed("chrn_1", "x")["status"], "completed")
        self.assertEqual(sum(1 for c in r.calls if c["method"] == "POST"), 1)
        self.assertTrue(all(c["url"].endswith(f"/v1/responses/{RID}") for c in r.calls[1:]))

    def test_replayed_stream_still_gives_ids(self):
        replay = frames([{"type": "response.created", "response": {"id": RID, "object": "response", "status": "completed", "output": []}},
                         {"type": "response.completed", "response": FINAL}])
        hr, _ = client(lambda c: FakeResponse(replay))
        seen = []
        hr.run_streamed("chrn_1", "x", on_ids=lambda rid, sid: seen.append(sid))
        self.assertEqual(seen, [SID])

    def test_errors_envelope_and_legacy(self):
        def route(c):
            if c["url"].endswith("/v1/nope"):
                return (404, {"detail": "Not Found"})
            return (409, {"error": {"type": "invalid_request_error", "code": "session_busy", "message": "busy", "param": "session_id"},
                          "detail": "busy"}, {"Retry-After": "3"})
        hr, _ = client(route)
        with self.assertRaises(hrm.HRError) as e:
            hr.request("GET", "/v1/nope")
        self.assertEqual((e.exception.status, e.exception.message, e.exception.code), (404, "Not Found", "not_found"))
        with self.assertRaises(hrm.HRError) as e:
            hr.request("POST", "/v1/responses", {})
        self.assertEqual((e.exception.code, e.exception.param, e.exception.retryable, e.exception.retry_after_seconds),
                         ("session_busy", "session_id", False, 3.0))

    def test_run_task_persists_publishes_settles_and_recover_polls(self):
        def route(c):
            if c["method"] == "POST":
                return FakeResponse(STREAM)
            if "/files" in c["url"]:
                return FakeResponse({"session_id": SID, "count": 2, "files": FILES})
            return FakeResponse(FINAL)
        hr, _ = client(route)
        store = hrm.MemoryTaskStore()
        got = []
        leave = hrm.subscribe("t1", lambda p: got.append(p["kind"]))
        done = hrm.run_task(hr, store, hrm.TaskRecord("t1", "u1", "chrn_1", "k"), "go")
        leave()
        self.assertEqual(done.status, "completed")
        self.assertEqual(done.answer, "Made two files.")
        self.assertEqual([f["path"] for f in done.files], ["site/index.html", "site/style.css"])
        self.assertEqual(got, ["activity", "text", "done"])
        store.put(replace(done, task_id="t2", status="in_progress"))
        self.assertEqual(hrm.recover_task(hr, store, "t2").status, "completed")

    def test_find_by_exact_name_and_if_match(self):
        def route(c):
            if c["method"] == "GET":
                return FakeResponse({"harnesses": [{"id": "chrn_1", "name": "Support replies"}, {"id": "chrn_2", "name": "Support replies v2"}]})
            return FakeResponse({"id": "chrn_1"})
        hr, r = client(route)
        self.assertEqual(hr.find_harness_by_name("Support replies")["id"], "chrn_1")
        self.assertIsNone(hr.find_harness_by_name("support replies"))
        hr.replace_harness("chrn_1", {"name": "Support replies", "base": "hermes"}, '"e1"')
        self.assertEqual(r.calls[-1]["headers"]["if-match"], '"e1"')


class PreviewTest(unittest.TestCase):
    def test_sign_and_verify(self):
        secret, now = b"\x07" * 32, 1_800_000_000
        tok = hrm.sign_preview("task_1", secret, 60, now)
        self.assertEqual(hrm.verify_preview(tok, secret, now), "task_1")
        self.assertIsNone(hrm.verify_preview(tok, b"\x08" * 32, now))
        self.assertIsNone(hrm.verify_preview(tok.replace("task_1", "task_2"), secret, now))
        self.assertIsNone(hrm.verify_preview(tok, secret, now + 61))
        self.assertIsNone(hrm.verify_preview("x.y.z", secret, now))
        with self.assertRaises(ValueError):
            hrm.sign_preview("a.b", secret)

    def test_safe_rel_path(self):
        self.assertEqual(hrm.safe_rel_path("css/app.css"), "css/app.css")
        for bad in ["../x", "a/../b", "/etc/passwd", "a\\b", "", "a//b", "%2e%2e/x", "a/./b"]:
            self.assertIsNone(hrm.safe_rel_path(bad), bad)

    def test_preview_and_download(self):
        def route(c):
            if c["url"].endswith("/files"):
                return FakeResponse({"session_id": SID, "count": 2, "files": FILES})
            return FakeResponse(b"<h1>Hi</h1>", {"Content-Type": "text/html", "Content-Disposition": 'attachment; filename="index.html"'})
        hr, r = client(route)
        st, hd, body = hrm.preview_file(hr, SID, "site", "index.html")
        self.assertEqual((st, body), (200, b"<h1>Hi</h1>"))
        self.assertEqual(hd["Content-Type"], "text/html; charset=utf-8")
        for k, v in hrm.PREVIEW_HEADERS.items():
            self.assertEqual(hd[k], v)
        self.assertTrue(any(c["url"] == f"https://api.harnessrouter.ai/v1/containers/{SID}/files/cfile_a/content" for c in r.calls))
        self.assertEqual(hrm.preview_file(hr, SID, "site", "missing.html")[0], 404)
        self.assertEqual(hrm.preview_file(hr, SID, "site", "../site/index.html")[0], 404)
        self.assertEqual(hrm.preview_file(hr, SID, "site", "run.exe")[0], 404)
        st, hd, _ = hrm.download_file(hr, SID, "site/style.css")
        self.assertEqual(hd["Content-Disposition"], 'attachment; filename="style.css"')


class KeyTest(unittest.TestCase):
    def test_load_api_key(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"HR_API_KEY": ""}):
            p = Path(d) / ".env.harnessrouter"
            p.write_text("HR_API_KEY=sk-hr-fromfile123\n")
            self.assertEqual(hrm.load_api_key(d), "sk-hr-fromfile123")
            p.write_text("HR_API_KEY=a\nOTHER=b\n")
            with self.assertRaises(ValueError):
                hrm.load_api_key(d)
            with mock.patch.dict(os.environ, {"HR_API_KEY": "sk-hr-fromenv1234"}):
                self.assertEqual(hrm.load_api_key(d), "sk-hr-fromenv1234")


if __name__ == "__main__":
    unittest.main()
