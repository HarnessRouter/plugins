# License: Apache-2.0; scope and full text: ../../LICENSING.md
"""HarnessRouter Cloud server adapter for Python 3.9+. Standard library only.

Copy this file into server-only code (FastAPI, Flask, Django, a worker). It covers: start a
streamed task, parse SSE, persist response.id and session_id, keep consuming after the browser
leaves, poll to recover, background mode, cancel, list and fetch files, and a signed sandboxed
preview route. Contract: references/api-reference.md (verified 2026-10-21, UHP-Version 2026-09-28).

The calls are blocking. In an async server run them in a thread (asyncio.to_thread, Starlette's
run_in_threadpool) or start run_task() in a background thread so it outlives the request.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

API_BASE = "https://api.harnessrouter.ai"
UHP_VERSION = "2026-09-28"
TERMINAL_STATUSES = frozenset({"completed", "incomplete", "failed", "cancelled"})
TERMINAL_EVENTS = frozenset({"response.completed", "response.incomplete", "response.failed"})

Json = Dict[str, Any]


class HRError(Exception):
    """A non-2xx answer: the UHP envelope, or the legacy {"detail": "..."} of an unknown route."""

    def __init__(self, status: int, body: Any = None, retry_after: Optional[str] = None):
        env = body if isinstance(body, dict) else {}
        err = env.get("error") if isinstance(env.get("error"), dict) else {}
        detail = env.get("detail") if isinstance(env.get("detail"), str) else ""
        self.status = status
        self.code = str(err.get("code") or ("not_found" if status == 404 else "unknown"))
        self.type = str(err.get("type") or "")
        self.param = err.get("param")
        self.message = str(err.get("message") or detail or f"HTTP {status}")
        try:
            self.retry_after_seconds: Optional[float] = float(retry_after) if retry_after else None
        except ValueError:
            self.retry_after_seconds = None
        super().__init__(self.message)

    @property
    def retryable(self) -> bool:
        """Only these are worth a retry (a POST /v1/responses only with the same Idempotency-Key)."""
        return self.status in (429, 502, 503, 504)


def load_api_key(project_root: str = ".") -> str:
    """HR_API_KEY, else the one-line .env.harnessrouter the key helper writes."""
    env = os.environ.get("HR_API_KEY", "").strip()
    if env:
        return env
    lines = [l for l in (Path(project_root) / ".env.harnessrouter").read_text().splitlines() if l.strip()]
    if len(lines) != 1 or not lines[0].startswith("HR_API_KEY="):
        raise ValueError(".env.harnessrouter must hold exactly one HR_API_KEY line")
    return lines[0][len("HR_API_KEY="):].strip()


def parse_sse(lines: Iterable[bytes]) -> Iterator[Json]:
    """Frames split on a blank line, data: lines joined, JSON parsed; [DONE] and junk skipped."""
    data: List[str] = []

    def flush() -> Optional[Json]:
        payload = "\n".join(data).strip()
        data.clear()
        if not payload or payload == "[DONE]":
            return None
        try:
            ev = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return ev if isinstance(ev, dict) and isinstance(ev.get("type"), str) else None

    for raw in lines:
        line = raw.decode("utf-8", "replace").rstrip("\r\n") if isinstance(raw, bytes) else str(raw).rstrip("\r\n")
        if line == "":
            ev = flush()
            if ev is not None:
                yield ev
        elif line.startswith("data:"):
            data.append(line[5:][1:] if line[5:].startswith(" ") else line[5:])
    ev = flush()
    if ev is not None:
        yield ev


def answer_text(r: Json) -> str:
    """The answer: the output_text of the LAST message item."""
    msgs = [i for i in r.get("output") or [] if i.get("type") == "message"]
    if not msgs:
        return ""
    return "".join(c.get("text") or "" for c in msgs[-1].get("content") or [] if c.get("type") == "output_text")


def produced_files(r: Json) -> List[Json]:
    """Files the task made or changed, as annotations (filename is the relative path)."""
    out = []
    for item in r.get("output") or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            out += [a for a in c.get("annotations") or [] if a.get("type") == "container_file_citation"]
    return out


def to_progress(ev: Json) -> Optional[Json]:
    """Upstream event -> the small, sanitized progress event a browser may see, or None."""
    t = ev.get("type")
    if t == "response.output_text.delta" and isinstance(ev.get("delta"), str):
        return {"kind": "text", "delta": ev["delta"]}
    item = ev.get("item") or {}
    if t == "response.output_item.added" and item.get("type") == "function_call":
        n = str(item.get("name") or "").lower()
        label = ("Writing files" if re.search(r"write|edit|patch", n) else "Reading files" if re.search(r"read|grep|glob|ls", n)
                 else "Running a step" if re.search(r"bash|shell|exec", n) else "Looking things up" if re.search(r"search|fetch|browse", n)
                 else "Working")
        return {"kind": "activity", "label": label}
    if t in TERMINAL_EVENTS:
        return {"kind": "done", "status": (ev.get("response") or {}).get("status") or "failed"}
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # never forward the key to another location
        return None


Opener = Callable[[urllib.request.Request, float], Any]


def _default_opener(req: urllib.request.Request, timeout: float):
    return urllib.request.build_opener(_NoRedirect()).open(req, timeout=timeout)


class HarnessRouter:
    def __init__(self, api_key: Optional[str] = None, base_url: str = API_BASE,
                 opener: Optional[Opener] = None, sleep: Callable[[float], None] = time.sleep):
        self._key = api_key if api_key is not None else load_api_key()
        self.base_url = base_url.rstrip("/")
        self._open = opener or _default_opener
        self._sleep = sleep

    # ── transport ──
    def _send(self, method: str, path: str, body: Any = None, headers: Optional[Dict[str, str]] = None,
              timeout: float = 60.0):
        h = {"Authorization": f"Bearer {self._key}", "UHP-Version": UHP_VERSION, "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=h)
        try:
            return self._open(req, timeout)
        except urllib.error.HTTPError as e:
            try:
                parsed = json.loads(e.read() or b"null")
            except ValueError:
                parsed = None
            raise HRError(e.code, parsed, e.headers.get("Retry-After") if e.headers else None) from None

    def request(self, method: str, path: str, body: Any = None, headers: Optional[Dict[str, str]] = None) -> Any:
        with self._send(method, path, body, headers) as res:
            return json.loads(res.read() or b"null")

    # ── catalog and harnesses ──
    def bases(self) -> Json:
        return self.request("GET", "/v1/bases")

    def me(self) -> Json:
        return self.request("GET", "/v1/me")

    def list_harnesses(self) -> List[Json]:
        return self.request("GET", "/v1/harnesses").get("harnesses") or []

    def find_harness_by_name(self, name: str) -> Optional[Json]:
        """"Reuse by name": the Harness whose name equals `name` exactly, if any."""
        return next((h for h in self.list_harnesses() if h.get("name") == name), None)

    def create_harness(self, body: Json) -> Json:
        return self.request("POST", "/v1/harnesses", body)

    def get_harness(self, harness_id: str):
        """(harness, etag)."""
        with self._send("GET", f"/v1/harnesses/{urllib.parse.quote(harness_id)}") as res:
            return json.loads(res.read()), res.headers.get("ETag")

    def replace_harness(self, harness_id: str, body: Json, etag: Optional[str] = None) -> Json:
        """A FULL replace: build `body` (snake_case) from a fresh get_harness() plus your change."""
        return self.request("PUT", f"/v1/harnesses/{urllib.parse.quote(harness_id)}", body,
                            {"If-Match": etag} if etag else None)

    def delete_harness(self, harness_id: str) -> Json:
        return self.request("DELETE", f"/v1/harnesses/{urllib.parse.quote(harness_id)}")

    # ── tasks ──
    @staticmethod
    def task_body(harness_id: str, input: Any, mode: str, previous_response_id: Optional[str] = None,
                  session_id: Optional[str] = None, **budgets: Any) -> Json:
        meta = {"harness_id": harness_id}
        if session_id:
            meta["session_id"] = session_id
        body: Json = {"input": input, "metadata": meta}
        if previous_response_id:
            body["previous_response_id"] = previous_response_id
        for k in ("max_step", "timeout_seconds", "max_cost_usd"):
            if budgets.get(k):
                body[k] = budgets[k]
        if mode == "stream":
            body["stream"] = True
        elif mode == "background":
            body["background"] = True
        return body

    def run_streamed(self, harness_id: str, input: Any, *, previous_response_id: Optional[str] = None,
                     session_id: Optional[str] = None, idempotency_key: Optional[str] = None,
                     on_ids: Optional[Callable[[str, str], None]] = None,
                     on_event: Optional[Callable[[Json], None]] = None, **budgets: Any) -> Json:
        """Start (or continue) a task and read its stream to the end; return the terminal response.
        A stream that ends without a terminal event is recovered by polling, never resent."""
        body = self.task_body(harness_id, input, "stream", previous_response_id, session_id, **budgets)
        res = self._send("POST", "/v1/responses", body,
                         {"Accept": "text/event-stream", "Idempotency-Key": idempotency_key or str(uuid.uuid4())},
                         timeout=budgets.get("timeout_seconds", 7200) + 300)
        response_id = sid = ""
        terminal: Optional[Json] = None
        try:
            with res:
                for ev in parse_sse(iter(res.readline, b"")):
                    r = ev.get("response") or {}
                    if r.get("id") and not response_id:
                        response_id = r["id"]
                    s = (r.get("metadata") or {}).get("session_id")
                    if s and not sid:
                        sid = s
                        # A replayed stream's created frame has no metadata: ids then come with the terminal event.
                        if on_ids:
                            on_ids(response_id, sid)
                    if on_event:
                        on_event(ev)
                    if ev.get("type") in TERMINAL_EVENTS and r:
                        terminal = r
        except (OSError, ValueError):
            if not response_id:
                raise
        if terminal:
            return terminal
        if not response_id:
            raise HRError(502, {"error": {"code": "stream_ended", "message": "The stream ended before the task started."}})
        return self.wait_for_response(response_id)

    def start_background(self, harness_id: str, input: Any, *, idempotency_key: Optional[str] = None, **kw: Any) -> Json:
        """Background mode: answers at once with status "in_progress"; poll with wait_for_response()."""
        return self.request("POST", "/v1/responses", self.task_body(harness_id, input, "background", **kw),
                            {"Idempotency-Key": idempotency_key or str(uuid.uuid4())})

    def get_response(self, response_id: str) -> Json:
        return self.request("GET", f"/v1/responses/{urllib.parse.quote(response_id)}")

    def wait_for_response(self, response_id: str, timeout_s: float = 7260.0) -> Json:
        """Poll until completed, incomplete, failed or cancelled: every 3 s, every 10 s after a minute."""
        start = time.monotonic()
        while True:
            try:
                r = self.get_response(response_id)
                if r.get("status") in TERMINAL_STATUSES:
                    return r
            except HRError as e:
                if not e.retryable:
                    raise
            elapsed = time.monotonic() - start
            if elapsed > timeout_s:
                raise HRError(504, {"error": {"code": "poll_timeout", "message": "The task did not finish in time."}})
            self._sleep(10.0 if elapsed > 60 else 3.0)

    def cancel_response(self, response_id: str) -> Json:
        return self.request("POST", f"/v1/responses/{urllib.parse.quote(response_id)}/cancel", {})

    def cancel_session(self, session_id: str) -> Json:
        return self.request("POST", f"/v1/sessions/{urllib.parse.quote(session_id)}/cancel", {})

    # ── files ──
    def list_files(self, session_id: str, changed: bool = False) -> List[Json]:
        q = "?changed=true" if changed else ""
        return self.request("GET", f"/v1/sessions/{urllib.parse.quote(session_id)}/files{q}").get("files") or []

    def fetch_file(self, session_id: str, file_id: str, view: str = "content"):
        """(bytes, content_type). The URL is built here, so the key only goes to the API origin."""
        path = f"/v1/containers/{urllib.parse.quote(session_id)}/files/{urllib.parse.quote(file_id)}/{view}"
        with self._send("GET", path, headers={"Accept": "*/*"}) as res:
            return res.read(), res.headers.get("Content-Type") or "application/octet-stream"


# ── tasks: persisted with the product's user, consumed independently of the browser ──────────
@dataclass
class TaskRecord:
    task_id: str
    user_id: str
    harness_id: str
    idempotency_key: str
    status: str = "starting"   # starting | in_progress | completed | incomplete | failed | cancelled
    response_id: str = ""
    session_id: str = ""
    answer: str = ""
    files: List[Json] = field(default_factory=list)
    incomplete_reason: str = ""
    updated_at: float = 0.0


class MemoryTaskStore:
    """Back this with the product's database. For development and tests only."""

    def __init__(self):
        self._m: Dict[str, TaskRecord] = {}
        self._lock = threading.Lock()

    def get(self, task_id: str) -> Optional[TaskRecord]:
        with self._lock:
            r = self._m.get(task_id)
            return replace(r) if r else None

    def put(self, rec: TaskRecord) -> None:
        with self._lock:
            self._m[rec.task_id] = replace(rec)


_listeners: Dict[str, List[Callable[[Json], None]]] = {}
_listeners_lock = threading.Lock()


def subscribe(task_id: str, fn: Callable[[Json], None]) -> Callable[[], None]:
    """Browser listener for one task. Leaving does not stop the task."""
    with _listeners_lock:
        _listeners.setdefault(task_id, []).append(fn)

    def leave():
        with _listeners_lock:
            fns = _listeners.get(task_id, [])
            if fn in fns:
                fns.remove(fn)
            if not fns:
                _listeners.pop(task_id, None)
    return leave


def _publish(task_id: str, p: Json) -> None:
    with _listeners_lock:
        fns = list(_listeners.get(task_id, []))
    for fn in fns:
        try:
            fn(p)
        except Exception:  # a broken listener never stops the task
            pass


def _settle(hr: HarnessRouter, store, rec: TaskRecord, r: Json) -> TaskRecord:
    sid = rec.session_id or (r.get("metadata") or {}).get("session_id") or ""
    files: List[Json] = []
    if sid and r.get("status") != "cancelled":
        try:
            files = hr.list_files(sid, changed=True)
        except HRError:
            files = []
    done = replace(rec, response_id=rec.response_id or r.get("id", ""), session_id=sid, status=r.get("status", "failed"),
                   answer=answer_text(r), files=files,
                   incomplete_reason=((r.get("incomplete_details") or {}).get("reason") or ""), updated_at=time.time())
    store.put(done)
    return done


def run_task(hr: HarnessRouter, store, rec: TaskRecord, input: Any,
             previous_response_id: Optional[str] = None, session_id: Optional[str] = None) -> TaskRecord:
    """Run one task for a product user to the end, persisting the ids at response.created and the
    result at the end. Start it in a background thread (start_task) so it outlives the request.
    For a follow-up pass previous_response_id and session_id from the stored record."""
    state = {"rec": replace(rec, updated_at=time.time())}
    store.put(state["rec"])

    def on_ids(response_id: str, sid: str) -> None:
        state["rec"] = replace(state["rec"], response_id=response_id, session_id=sid, status="in_progress", updated_at=time.time())
        store.put(state["rec"])

    def on_event(ev: Json) -> None:
        p = to_progress(ev)
        if p:
            _publish(rec.task_id, p)

    try:
        r = hr.run_streamed(rec.harness_id, input, previous_response_id=previous_response_id, session_id=session_id,
                            idempotency_key=rec.idempotency_key, on_ids=on_ids, on_event=on_event)
        return _settle(hr, store, state["rec"], r)
    except HRError:
        failed = replace(state["rec"], status="failed", updated_at=time.time())
        store.put(failed)
        _publish(rec.task_id, {"kind": "done", "status": "failed"})
        return failed


def start_task(hr: HarnessRouter, store, rec: TaskRecord, input: Any, **follow_up: Any) -> threading.Thread:
    """run_task in a daemon thread: the request handler returns at once; the task runs to its end."""
    t = threading.Thread(target=run_task, args=(hr, store, rec, input), kwargs=follow_up, daemon=True)
    t.start()
    return t


def recover_task(hr: HarnessRouter, store, task_id: str) -> Optional[TaskRecord]:
    """After a restart: finish a record that has a response_id but no terminal status, by polling."""
    rec = store.get(task_id)
    if not rec or not rec.response_id or rec.status in TERMINAL_STATUSES:
        return rec
    return _settle(hr, store, rec, hr.wait_for_response(rec.response_id))


# ── signed, sandboxed previews (files-artifacts-and-rendering.md) ─────────────────────────────
_process_secret = secrets.token_bytes(32)


def preview_secret() -> bytes:
    """PREVIEW_SIGNING_SECRET (hex or base64, 32 bytes) from the server env; else a per-process
    random secret, fine in development (links stop working after a restart)."""
    v = os.environ.get("PREVIEW_SIGNING_SECRET", "").strip()
    if v:
        return bytes.fromhex(v) if re.fullmatch(r"[0-9a-fA-F]{64}", v) else base64.b64decode(v)
    return _process_secret


def _mac(secret: bytes, msg: str) -> str:
    return base64.urlsafe_b64encode(hmac.new(secret, msg.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()


def sign_preview(task_id: str, secret: Optional[bytes] = None, ttl_seconds: int = 3600, now: Optional[float] = None) -> str:
    """"<task_id>.<expires_at>.<signature>", for /preview/<token>/index.html. No dots in task_id."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        raise ValueError("task_id must be [A-Za-z0-9_-]")
    exp = int(now if now is not None else time.time()) + ttl_seconds
    return f"{task_id}.{exp}.{_mac(secret or preview_secret(), f'{task_id}.{exp}')}"


def verify_preview(token: str, secret: Optional[bytes] = None, now: Optional[float] = None) -> Optional[str]:
    """The task_id when the token is genuine and unexpired, else None. Constant-time comparison."""
    m = re.fullmatch(r"([A-Za-z0-9_-]{1,128})\.(\d{1,12})\.([A-Za-z0-9_-]{43})", token or "")
    if not m:
        return None
    task_id, exp, sig = m.groups()
    if int(exp) < (now if now is not None else time.time()):
        return None
    want = _mac(secret or preview_secret(), f"{task_id}.{exp}")
    return task_id if hmac.compare_digest(want, sig) else None


PREVIEW_TYPES = {
    "html": "text/html; charset=utf-8", "htm": "text/html; charset=utf-8", "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8", "mjs": "text/javascript; charset=utf-8", "json": "application/json",
    "txt": "text/plain; charset=utf-8", "md": "text/plain; charset=utf-8", "svg": "image/svg+xml", "png": "image/png",
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "ico": "image/x-icon",
    "woff": "font/woff", "woff2": "font/woff2", "ttf": "font/ttf", "otf": "font/otf",
}
PREVIEW_HEADERS = {
    "Content-Security-Policy": "sandbox allow-scripts allow-forms; default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "private, no-store",
}
_NOT_FOUND = (404, {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}, b"Not found")


def safe_rel_path(p: str) -> Optional[str]:
    """A relative path inside the output folder, or None for anything that could escape it."""
    s = urllib.parse.unquote(p or "")
    if not s or "\\" in s or "\0" in s or s.startswith("/"):
        return None
    parts = s.split("/")
    if any(x in ("", ".", "..") for x in parts):
        return None
    return "/".join(parts)


def preview_file(hr: HarnessRouter, session_id: str, root: str, rel_path: str):
    """(status, headers, body) for the preview route, after verify_preview() gave a task_id and the
    product loaded its record: <root>/<rel_path> from the session's files, with the sandbox CSP."""
    rel = safe_rel_path(rel_path or "index.html")
    if not rel:
        return _NOT_FOUND
    ctype = PREVIEW_TYPES.get(rel.rsplit(".", 1)[-1].lower() if "." in rel else "")
    if not ctype:
        return _NOT_FOUND
    want = f"{root.rstrip('/')}/{rel}" if root else rel
    f = next((x for x in hr.list_files(session_id) if x.get("path") == want), None)
    if not f:
        return _NOT_FOUND
    body, _ = hr.fetch_file(session_id, f["id"])
    return 200, {**PREVIEW_HEADERS, "Content-Type": ctype}, body


def download_file(hr: HarnessRouter, session_id: str, path: str):
    """(status, headers, body) for the download route (owner already checked)."""
    f = next((x for x in hr.list_files(session_id) if x.get("path") == path), None)
    if not f:
        return _NOT_FOUND
    body, ctype = hr.fetch_file(session_id, f["id"])
    name = re.sub(r'["\r\n\\]', "_", f.get("filename") or "download")
    return 200, {"Content-Type": ctype, "Content-Disposition": f'attachment; filename="{name}"',
                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"}, body
