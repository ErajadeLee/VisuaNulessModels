"""Windows packaging checks: isolated imports, real launchers, port fallback and relocation.

Run with: runtime/python/python.exe -I -S -B -X utf8 tests/portable_smoke.py
This opens and closes only this application's own test windows.
"""
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import ProxyHandler, build_opener

import launcher

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "preview/portable-checks.json"
CHECKS = []
DETAILS = {}


def wait_until(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.15)
    raise AssertionError("Timed out: " + predicate.__name__)


def poisoned_environment(root):
    environment = os.environ.copy()
    environment["PATH"] = str(root / "unavailable-system-programs")
    environment["PYTHONHOME"] = str(root / "unavailable-python-home")
    environment["PYTHONPATH"] = str(root / "unavailable-python-packages")
    environment["HTTP_PROXY"] = environment["HTTPS_PROXY"] = "http://127.0.0.1:9"
    directory = root / ".run/temp"
    directory.mkdir(parents=True, exist_ok=True)
    environment["TEMP"] = environment["TMP"] = str(directory)
    return environment


def python_call(root, arguments, timeout=35):
    return subprocess.run(
        [str(root / "runtime/python/python.exe"), "-I", "-S", "-B", "-X", "utf8"] + arguments,
        cwd=os.environ.get("SystemRoot", r"C:\Windows"),
        env=poisoned_environment(root), capture_output=True, encoding="utf-8", timeout=timeout,
        check=True)


def get(state, path):
    with build_opener(ProxyHandler({})).open(
            "http://127.0.0.1:{}{}".format(state["port"], path), timeout=5) as response:
        return response.read()


def pid_active(pid):
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    exit_code = wintypes.DWORD()
    try:
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel.CloseHandle(handle)


def window_title(pid):
    from ctypes import wintypes
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    titles = []
    def visit(handle, unused):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(handle):
            title = ctypes.create_unicode_buffer(512)
            user.GetWindowTextW(handle, title, len(title))
            titles.append(title.value)
        return True
    user.EnumWindows(callback_type(visit), 0)
    return next((title for title in titles if "模型探索工作台" in title or "Model Explorer" in title), None)


def launch_native(root, filename=launcher.APP_ENTRY):
    result = subprocess.run([str(root / filename)], cwd=os.environ.get("SystemRoot", r"C:\Windows"),
                            env=poisoned_environment(root), timeout=5, check=True)
    assert result.returncode == 0


def await_instance(root, window=False):
    def ready():
        state = launcher.existing_instance(root)
        if state and (not window or state.get("browser_pid")):
            return state
        return None
    return wait_until(ready)


def await_closed(root, state):
    def closed():
        return not pid_active(state["pid"]) and not (root / ".run/state.json").exists()
    wait_until(closed, timeout=20)
    if state.get("browser_pid"):
        assert not pid_active(state["browser_pid"])


def isolation_check(root):
    # Reject every Python-level application file read outside the relocated copy,
    # including reads of the original D:\0nbb_Visualization.
    code = r'''
import json, os, sys
from pathlib import Path
root = Path(sys.executable).resolve().parents[2]
opened = set()
def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        path.relative_to(root)
        opened.add(str(path.relative_to(root)))
sys.addaudithook(audit)
from matching import MatchingEngine
from matching.server import create_server
from urllib.request import ProxyHandler, build_opener
import threading
engine = MatchingEngine.from_file()
server = create_server(engine, port=0)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
try:
    base = "http://127.0.0.1:" + str(server.server_port)
    opener = build_opener(ProxyHandler({}))
    def fetch(route):
        with opener.open(base + route, timeout=8) as response:
            return response.read()
    assert len(json.loads(fetch("/api/fields"))["fields"]) == 61
    match = json.loads(fetch("/api/match?fields=1,52,56"))
    assert match["generation"]["model_field_ids"] == ["MF-3i-23"]
    assert match["generation"]["diagram_count"] == 7
    packet = json.loads(fetch("/api/attachments/T1-1-1"))
    assert packet["model_field_id"] == "MF-4i-155"
    for stage in ("topology", "diagram", "attachment"):
        assert b"<svg" in fetch("/api/attachments/T1-1-1.svg?stage=" + stage)
    for resource in ("/", "/assets/app.css", "/assets/app.js", "/assets/i18n.js", "/assets/attachment.js",
                     "/assets/app-icon.svg", "/favicon.ico", "/attachment"):
        assert fetch(resource)
    result = {"status": "ok", "root": str(root), "module_paths": sys.path,
              "file_read_count": len(opened), "opened_files": sorted(opened),
              **engine.validate_attachments()}
    assert all(Path(path).resolve().is_relative_to(root) for path in sys.path)
    print(json.dumps(result, ensure_ascii=False))
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
'''
    result = json.loads(python_call(root, ["-c", code]).stdout)
    assert result["validated_model_diagram_count"] == 5280
    assert "data\\catalog.json" in result["opened_files"]
    assert "data\\topologies.json" in result["opened_files"]
    return result


def service_check(root=ROOT):
    assert launcher.existing_instance(root) is None, "Close the current application before running this check"
    occupied = socket.socket()
    occupied.bind(("127.0.0.1", 0))
    occupied.listen(1)
    occupied_port = occupied.getsockname()[1]
    process = subprocess.Popen(
        [str(root / "runtime/python/python.exe"), "-I", "-S", "-B", "-X", "utf8", str(root / "launcher.py"),
         "--no-browser", "--port", str(occupied_port)],
        cwd=os.environ.get("SystemRoot", r"C:\Windows"), env=poisoned_environment(root),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    state = None
    try:
        state = await_instance(root)
        assert state["pid"] == process.pid
        assert state["port"] != occupied_port
        CHECKS.append("occupied port falls back without stopping any other program")
        duplicate = python_call(root, [str(root / "launcher.py"), "--no-browser"])
        again = launcher.existing_instance(root)
        assert again["pid"] == state["pid"] and again["port"] == state["port"]
        assert "127.0.0.1:" in duplicate.stdout
        CHECKS.append("duplicate startup reuses the authenticated instance in the same folder")
        bad = dict(state)
        bad["token"] = "wrong-token"
        try:
            launcher.local_request(bad, "/api/stop", method="POST")
            raise AssertionError("Unauthenticated shutdown was accepted")
        except HTTPError as exc:
            assert exc.code == 403
        assert json.loads(get(state, "/api/fields"))["statistics"]["diagram_count"] == 5280
        CHECKS.append("shutdown requires this folder's instance token")
        python_call(root, [str(root / "launcher.py"), "--stop"])
        await_closed(root, state)
        assert process.wait(timeout=5) == 0
        CHECKS.append("authenticated internal shutdown cleans up the service without a separate stop executable")
    finally:
        occupied.close()
        if state and process.poll() is None:
            launcher.stop_application(root)
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=8)


def window_check(root):
    state = None
    try:
        launch_native(root)
        state = await_instance(root, window=True)
        title = wait_until(lambda: window_title(state["browser_pid"]), timeout=30)
        assert state["root"] == str(root.resolve())
        assert json.loads(get(state, "/api/match?fields=1,52,56"))["generation"]["diagram_count"] == 7
        launch_native(root)
        again = await_instance(root, window=True)
        assert again["pid"] == state["pid"]
        assert again["browser_pid"] == state["browser_pid"]
        time.sleep(0.3)
        launcher.window_action(state["browser_pid"], close=True)
        await_closed(root, state)
        return {"root": str(root), "window_title": title, "mode": state["mode"]}
    finally:
        if launcher.existing_instance(root):
            launcher.stop_application(root)


def relocation_check():
    test_area = ROOT / "_portable-test"
    relocated = test_area / "复制后的独立程序 with spaces"
    assert not relocated.exists(), "Remove the previous test copy before repeating relocation checks"
    relocated.mkdir(parents=True)
    try:
        for directory in ("runtime", "data", "matching"):
            shutil.copytree(ROOT / directory, relocated / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (relocated / "preview").mkdir()
        for name in ("index.html", "attachment.html", "app.css", "app.js", "i18n.js", "attachment.js",
                     "app-icon.svg", "app-icon.ico"):
            shutil.copy2(ROOT / "preview" / name, relocated / "preview" / name)
        for name in ("launcher.py", launcher.APP_ENTRY):
            shutil.copy2(ROOT / name, relocated / name)
        DETAILS["relocated_isolation"] = isolation_check(relocated)
        CHECKS.append("relocated copy reads every application file only from its own folder")
        service_check(relocated)
        DETAILS["relocated_window"] = window_check(relocated)
        CHECKS.append("the single renamed executable works from a Chinese path with spaces and poisoned Python/PATH/proxy settings")
    finally:
        # The resolved recursive-delete target must remain within this exact test area.
        resolved = relocated.resolve()
        resolved.relative_to(test_area.resolve())
        assert resolved != test_area.resolve() and resolved.parent == test_area.resolve()
        if launcher.existing_instance(relocated):
            launcher.stop_application(relocated)
        shutil.rmtree(resolved)
        if test_area.exists() and not any(test_area.iterdir()):
            test_area.rmdir()


def main():
    if os.name != "nt":
        raise RuntimeError("This package targets Windows x64")
    try:
        DETAILS["original_isolation"] = isolation_check(ROOT)
        CHECKS.append("local runtime and complete HTTP/attachment pipeline ignore all external Python and data sources")
        assert [file.name for file in ROOT.glob("*.exe")] == [launcher.APP_ENTRY]
        assert not list(ROOT.glob("*.cmd"))
        DETAILS["original_window"] = {
            "existing_instance_preserved": launcher.existing_instance(ROOT) is not None,
            "native_checks": "relocated_copy",
        }
        CHECKS.append("the application exposes one renamed executable and no command launchers")
        CHECKS.append("native launch checks use an isolated copy and preserve the original application's state")
        relocation_check()
        result = {"status": "ok", "checks": CHECKS, "details": DETAILS}
    except Exception as exc:
        result = {"status": "failed", "error": repr(exc), "checks": CHECKS, "details": DETAILS}
        REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks": CHECKS}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
