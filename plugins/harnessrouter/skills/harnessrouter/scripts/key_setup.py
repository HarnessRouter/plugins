#!/usr/bin/env python3
"""Local macOS candidate. Return status only; never include key data in arguments or output."""
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
DIALOG = 'text returned of (display dialog "Paste your HarnessRouter API key (sk-hr-). Stored only in this project server environment." default answer "" with hidden answer buttons {"Cancel", "Save"} default button "Save" cancel button "Cancel")'

def destination(project):
    requested = Path(project).absolute()
    if requested.is_symlink():
        raise ValueError("UNSAFE_DESTINATION")
    root = requested.resolve()
    for part in [root, *root.parents]:
        if part.is_symlink():
            raise ValueError("UNSAFE_DESTINATION")
    target = root / FILE_NAME
    ignore = root / ".gitignore"
    if not root.is_dir() or target.is_symlink() or ignore.is_symlink():
        raise ValueError("UNSAFE_DESTINATION")
    git = subprocess.run(["git","-C",str(root),"rev-parse","--show-toplevel"], capture_output=True)
    if git.returncode:
        raise ValueError("UNSAFE_DESTINATION")
    tracked = subprocess.run(["git","-C",str(root),"ls-files","--error-unmatch",FILE_NAME],capture_output=True)
    if tracked.returncode == 0:
        raise ValueError("UNSAFE_DESTINATION")
    if target.exists() and (not target.is_file() or target.stat().st_mode & 0o077):
        raise ValueError("UNSAFE_DESTINATION")
    return root, target, ignore

def read_key(target):
    if not target.exists():
        return ""
    if target.stat().st_size > 8192:
        raise ValueError("UNSAFE_DESTINATION")
    content = target.read_text()
    lines = content.splitlines()
    # This helper owns a dedicated single-variable file, not a general dotenv parser.
    if len(lines) != 1 or not lines[0].startswith(ENV_NAME+"="):
        raise ValueError("UNSAFE_DESTINATION")
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
        p = subprocess.run(["osascript","-e",DIALOG],capture_output=True,timeout=120)
    except (OSError,subprocess.TimeoutExpired):
        return "INPUT_UNAVAILABLE", None
    if p.returncode:
        return ("CANCELLED" if b"(-128)" in p.stderr else "INPUT_UNAVAILABLE"), None
    try:
        value = p.stdout.decode().strip()
    except UnicodeDecodeError:
        return "INVALID_FORMAT", None
    if not re.fullmatch(r"sk-hr-[A-Za-z0-9_-]{8,}", value):
        return "INVALID_FORMAT", None
    return "KEY_SAVED", value

def collect(project, server_load_confirmed=False):
    if current(project) == "READY":
        return "READY"
    if not server_load_confirmed:
        return "UNSAFE_DESTINATION"
    root, target, ignore = destination(project)
    status, value = prompt()
    if status != "KEY_SAVED":
        return status
    if not isinstance(value,str) or not re.fullmatch(r"sk-hr-[A-Za-z0-9_-]{8,}",value):
        return "INVALID_FORMAT"
    # Recheck before writing, never replace a credential that appeared while the dialog was open.
    destination(project)
    if read_key(target).strip():
        return "READY"
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
        # No plaintext tempfile remains after success/failure.
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return "KEY_SAVED"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def http_status(key):
    request = urllib.request.Request("https://api.harnessrouter.ai/v1/models",
        headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    # Do not read or print bodies/headers, even on error. Do not follow redirects.
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError,TimeoutError,OSError):
        return 0

def verify(project):
    key = os.environ.get(ENV_NAME,"")
    if not key.strip():
        _, target, _ = destination(project)
        key = read_key(target)
    if not key.strip():
        return "MISSING"
    status = http_status(key)
    if status == 200: return "CONNECTED"
    if status == 401: return "UNAUTHORIZED"
    if status == 403: return "FORBIDDEN"
    if status == 429: return "RATE_LIMITED"
    if 500 <= status <= 599: return "SERVICE_UNAVAILABLE"
    if status == 0: return "CONNECTION_UNAVAILABLE"
    return "CONFIGURATION_ERROR"

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["check","collect","verify"])
    p.add_argument("--project",required=True)
    p.add_argument("--server-load-confirmed",action="store_true")
    a = p.parse_args()
    try:
        status = current(a.project) if a.action=="check" else (
            collect(a.project,a.server_load_confirmed) if a.action=="collect" else verify(a.project))
    except ValueError:
        status = "UNSAFE_DESTINATION"
    except Exception:
        # Never print exception text: transports and files may include secret-bearing content.
        status = "SAVE_FAILED" if a.action=="collect" else "CONNECTION_UNAVAILABLE"
    print(json.dumps({"status":status}))
    return 0 if status in ("READY","MISSING","KEY_SAVED","CONNECTED","CANCELLED") else 2

if __name__ == "__main__":
    raise SystemExit(main())
