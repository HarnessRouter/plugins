#!/usr/bin/env python3
"""HarnessRouter Cloud key helper. Prints one JSON object with a status (and a plain next step);
never prints, logs or passes the key.

  check   --project P                          READY | MISSING | NOT_A_GIT_REPO | UNSAFE_DESTINATION
  collect --project P --server-load-confirmed  KEY_SAVED | READY | CANCELLED | INPUT_UNAVAILABLE | ...
  replace --project P --server-load-confirmed  KEY_REPLACED | CANCELLED | INPUT_UNAVAILABLE | ...
  verify  --project P                          CONNECTED | UNAUTHORIZED | FORBIDDEN | ...

Preconditions (each reported by its own status): the project is inside a git repository
(NOT_A_GIT_REPO), the product server reads .env.harnessrouter (SERVER_LOAD_UNCONFIRMED until
--server-load-confirmed), and the hidden-entry prompt exists only on macOS (INPUT_UNAVAILABLE
elsewhere). See references/key-setup.md.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

ENV_NAME = "HR_API_KEY"
FILE_NAME = ".env.harnessrouter"
API = "https://api.harnessrouter.ai"
KEY_RE = r"sk-hr-[A-Za-z0-9_-]{8,}"
DIALOG = '''
const app = Application.currentApplication();
app.includeStandardAdditions = true;
const result = app.displayDialog(
  "Paste your HarnessRouter API key (sk-hr-). It will be stored only in this project's server environment.",
  {
    defaultAnswer: "",
    hiddenAnswer: true,
    buttons: ["Cancel", "Save"],
    defaultButton: "Save",
    cancelButton: "Cancel"
  }
);
result.textReturned;
'''

NEXT = {
    "READY": "A key is available. Run verify before the first API call.",
    "MISSING": "No key yet. Make sure the product server reads .env.harnessrouter, then run collect --server-load-confirmed.",
    "NOT_A_GIT_REPO": "The project is not a git repository, so the key file cannot be kept out of commits. For a new project run git init in its root, then run this again.",
    "SERVER_LOAD_UNCONFIRMED": "Add the server-side loader for .env.harnessrouter (references/key-setup.md), then run this again with --server-load-confirmed.",
    "UNSAFE_DESTINATION": "The key file location is unsafe (see reason). Fix it, then run this again.",
    "KEY_SAVED": "Saved to .env.harnessrouter (owner-only, ignored by git). Run verify.",
    "KEY_REPLACED": "Replaced. Run verify.",
    "CANCELLED": "The user cancelled. Do not open the prompt again unless they ask.",
    "INPUT_UNAVAILABLE": "This host has no trusted hidden prompt (macOS only). Continue without a key and tell the user the key must reach the server environment as HR_API_KEY through a secret store they already use; then run check again.",
    "INVALID_FORMAT": "That was not an sk-hr- key. Nothing was saved. Ask the user whether to try again.",
    "SAVE_FAILED": "The key could not be saved. Nothing was changed.",
    "CONNECTED": "The key works.",
    "UNAUTHORIZED": "The saved key was rejected. Tell the user; with their go-ahead run replace --server-load-confirmed.",
    "FORBIDDEN": "The key cannot read this. Check its Workspace and permissions; keep the key.",
    "RATE_LIMITED": "Rate limited. Wait and run verify again; do not prompt for a new key.",
    "SERVICE_UNAVAILABLE": "The service is unavailable. Try again later; do not prompt for a new key.",
    "CONNECTION_UNAVAILABLE": "No connection to api.harnessrouter.ai. Check the network; do not prompt for a new key.",
    "CONFIGURATION_ERROR": "Unexpected answer (redirect or other). Do not forward the key anywhere else.",
}
OK_STATUSES = ("READY", "MISSING", "KEY_SAVED", "KEY_REPLACED", "CONNECTED", "CANCELLED")


class Refused(ValueError):
    """A precondition failed: status is one of NOT_A_GIT_REPO, UNSAFE_DESTINATION."""

    def __init__(self, status, reason=""):
        super().__init__(status)
        self.status, self.reason = status, reason


def destination(project):
    requested = Path(project).absolute()
    if requested.is_symlink():
        raise Refused("UNSAFE_DESTINATION", "symlink")
    root = requested.resolve()
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise Refused("UNSAFE_DESTINATION", "symlink")
    target = root / FILE_NAME
    ignore = root / ".gitignore"
    if not root.is_dir():
        raise Refused("UNSAFE_DESTINATION", "not_a_directory")
    if target.is_symlink() or ignore.is_symlink():
        raise Refused("UNSAFE_DESTINATION", "symlink")
    git = subprocess.run(["git","-C",str(root),"rev-parse","--show-toplevel"], capture_output=True)
    if git.returncode:
        raise Refused("NOT_A_GIT_REPO")
    tracked = subprocess.run(["git","-C",str(root),"ls-files","--error-unmatch",FILE_NAME],capture_output=True)
    if tracked.returncode == 0:
        raise Refused("UNSAFE_DESTINATION", "tracked_by_git")
    if target.exists() and (not target.is_file() or target.stat().st_mode & 0o077):
        raise Refused("UNSAFE_DESTINATION", "permissions")
    return root, target, ignore

def read_key(target):
    if not target.exists():
        return ""
    if target.stat().st_size > 8192:
        raise Refused("UNSAFE_DESTINATION", "format")
    content = target.read_text()
    lines = content.splitlines()
    # This helper owns a dedicated single-variable file, not a general dotenv parser.
    if len(lines) != 1 or not lines[0].startswith(ENV_NAME+"="):
        raise Refused("UNSAFE_DESTINATION", "format")
    return lines[0][len(ENV_NAME)+1:]

def current(project):
    if os.environ.get(ENV_NAME, "").strip():
        return "READY"
    _, target, _ = destination(project)
    return "READY" if read_key(target).strip() else "MISSING"

def prompt():
    if sys.platform != "darwin":
        return "INPUT_UNAVAILABLE", None
    try:
        p = subprocess.run(["osascript","-l","JavaScript","-e",DIALOG],capture_output=True,timeout=120)
    except KeyboardInterrupt:
        return "CANCELLED", None
    except (OSError,subprocess.TimeoutExpired):
        return "INPUT_UNAVAILABLE", None
    if p.returncode:
        return ("CANCELLED" if b"(-128)" in p.stderr else "INPUT_UNAVAILABLE"), None
    try:
        value = p.stdout.decode().strip()
    except UnicodeDecodeError:
        return "INVALID_FORMAT", None
    if not re.fullmatch(KEY_RE, value):
        return "INVALID_FORMAT", None
    return "KEY_SAVED", value

def write_key(root, target, ignore, value):
    old_ignore = ignore.read_text() if ignore.exists() else ""
    check = subprocess.run(["git","-C",str(root),"check-ignore","--quiet",FILE_NAME],capture_output=True)
    if check.returncode:
        ignore.write_text(old_ignore + ("\n" if old_ignore and not old_ignore.endswith("\n") else "") + "/"+FILE_NAME+"\n")
    fd, temp = tempfile.mkstemp(prefix=".hr-key-",dir=root)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w") as f:
            f.write(ENV_NAME+"="+value+"\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def collect(project, server_load_confirmed=False):
    if current(project) == "READY":
        return "READY"
    if not server_load_confirmed:
        return "SERVER_LOAD_UNCONFIRMED"
    root, target, ignore = destination(project)
    status, value = prompt()
    if status != "KEY_SAVED":
        return status
    if not isinstance(value,str) or not re.fullmatch(KEY_RE,value):
        return "INVALID_FORMAT"
    # Recheck before writing, never replace a credential that appeared while the dialog was open.
    destination(project)
    if read_key(target).strip():
        return "READY"
    write_key(root, target, ignore, value)
    return "KEY_SAVED"

def replace(project, server_load_confirmed=False):
    root, target, ignore = destination(project)
    if not server_load_confirmed:
        return "SERVER_LOAD_UNCONFIRMED"
    status, value = prompt()
    if status != "KEY_SAVED":
        return status
    if not isinstance(value,str) or not re.fullmatch(KEY_RE,value):
        return "INVALID_FORMAT"
    destination(project)
    write_key(root, target, ignore, value)
    return "KEY_REPLACED"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def http_get(key, path):
    """(status, parsed JSON body or None). The body is read only on 200 and never printed whole."""
    request = urllib.request.Request(API + path,
        headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
            try:
                return response.status, json.loads(response.read(65536))
            except ValueError:
                return response.status, None
    except urllib.error.HTTPError as error:
        return error.code, None
    except (urllib.error.URLError,TimeoutError,OSError):
        return 0, None

def verify(project):
    key = os.environ.get(ENV_NAME,"")
    if not key.strip():
        _, target, _ = destination(project)
        key = read_key(target)
    if not key.strip():
        return "MISSING", {}
    status, body = http_get(key.strip(), "/v1/me")
    if status == 200:
        name = body.get("workspace_name") if isinstance(body, dict) else None
        return "CONNECTED", ({"workspace_name": str(name)} if name else {})
    if status == 401: return "UNAUTHORIZED", {}
    if status == 403: return "FORBIDDEN", {}
    if status == 429: return "RATE_LIMITED", {}
    if 500 <= status <= 599: return "SERVICE_UNAVAILABLE", {}
    if status == 0: return "CONNECTION_UNAVAILABLE", {}
    return "CONFIGURATION_ERROR", {}

def run(action, project, confirmed):
    extra = {}
    try:
        if action == "check":
            status = current(project)
        elif action == "collect":
            status = collect(project, confirmed)
        elif action == "replace":
            status = replace(project, confirmed)
        else:
            status, extra = verify(project)
    except Refused as refused:
        status = refused.status
        if refused.reason:
            extra = {"reason": refused.reason}
    except Exception:
        # Never print exception text: transports and files may include secret-bearing content.
        status = "SAVE_FAILED" if action in ("collect","replace") else "CONNECTION_UNAVAILABLE"
    return {"status": status, **extra, "next": NEXT.get(status, "")}

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["check","collect","replace","verify"])
    p.add_argument("--project",required=True)
    p.add_argument("--server-load-confirmed",action="store_true")
    a = p.parse_args()
    result = run(a.action, a.project, a.server_load_confirmed)
    print(json.dumps(result))
    return 0 if result["status"] in OK_STATUSES else 2

if __name__ == "__main__":
    raise SystemExit(main())
