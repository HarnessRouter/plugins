#!/usr/bin/env python3
# License: Apache-2.0; scope and full text: ../../LICENSING.md
"""Live end-to-end check of harnessrouter.py: one real streamed task, ids persisted at
response.created, recovery by polling, file list, a signed sandboxed preview and a download.

  python3 templates/python/e2e.py --project <dir with .env.harnessrouter> --harness chrn_…

The key comes from HR_API_KEY or <project>/.env.harnessrouter; it is never printed.
"""
import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harnessrouter as hrm  # noqa: E402


class WatchedStore(hrm.MemoryTaskStore):
    ids_before_end = False

    def put(self, rec):
        if rec.response_id and rec.session_id and rec.status == "in_progress":
            self.ids_before_end = True
        super().put(rec)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default=".")
    ap.add_argument("--harness", default=os.environ.get("HR_HARNESS_ID", ""))
    a = ap.parse_args()
    if not a.harness:
        print(json.dumps({"ok": False, "error": "pass --harness or HR_HARNESS_ID"}))
        return 2
    hr = hrm.HarnessRouter(api_key=hrm.load_api_key(a.project))
    me = hr.me()
    store = WatchedStore()
    task_id = uuid.uuid4().hex
    rec = hrm.TaskRecord(task_id=task_id, user_id="e2e", harness_id=a.harness, idempotency_key=str(uuid.uuid4()))
    progress = []
    leave = hrm.subscribe(task_id, progress.append)
    t0 = time.time()
    done = hrm.run_task(hr, store, rec, "Write site/index.html with an h1 that says Hello and a stylesheet link to "
                                        "style.css, and site/style.css that makes the h1 blue. Then reply with one short line.")
    leave()
    checks = {}
    checks["completed"] = done.status == "completed"
    checks["ids_saved_at_created"] = store.ids_before_end
    checks["answer"] = bool(done.answer)
    checks["progress_events"] = len(progress) > 0
    paths = [f["path"] for f in done.files]
    checks["files_listed"] = "site/index.html" in paths and "site/style.css" in paths

    store.put(replace(done, task_id=task_id + "r", status="in_progress"))
    checks["recover_by_polling"] = (hrm.recover_task(hr, store, task_id + "r") or done).status == "completed"

    token = hrm.sign_preview(task_id)
    checks["preview_token"] = hrm.verify_preview(token) == task_id and hrm.verify_preview(token[:-2] + "xx") is None
    st, hd, body = hrm.preview_file(hr, done.session_id, "site", "index.html")
    checks["preview_html"] = st == 200 and hd.get("Content-Security-Policy") == hrm.PREVIEW_HEADERS["Content-Security-Policy"] and b"<h1" in body.lower()
    st2, hd2, _ = hrm.preview_file(hr, done.session_id, "site", "style.css")
    checks["preview_css"] = st2 == 200 and hd2["Content-Type"].startswith("text/css")
    checks["preview_rejects_escape"] = hrm.preview_file(hr, done.session_id, "site", "../site/index.html")[0] == 404
    st3, hd3, _ = hrm.download_file(hr, done.session_id, "site/index.html")
    checks["download_attachment"] = st3 == 200 and hd3.get("Content-Disposition", "").startswith("attachment;")

    ok = all(checks.values())
    print(json.dumps({"ok": ok, "workspace": me.get("workspace_name"), "status": done.status,
                      "seconds": round(time.time() - t0), "files": paths, "progress_events": len(progress),
                      "answer_chars": len(done.answer), "checks": checks}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
