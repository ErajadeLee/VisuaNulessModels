"""Portable desktop entry point. Every application path is relative to this file."""
import argparse
import ctypes
import errno
import json
import logging
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
APP_ID = "0nbb-visualization"
APP_NAME = "0νββ 模型探索"
APP_ENTRY = APP_NAME + ".exe"
LOGGER = logging.getLogger(APP_ID)


class InstanceLock:
    """A per-folder OS lock; an interrupted process cannot leave a stale lock."""
    def __init__(self, path):
        self.path = Path(path)
        self.stream = None

    def acquire(self):
        stream = self.path.open("a+b")
        if stream.seek(0, 2) == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.stream = stream
        return True

    def release(self):
        if self.stream is not None:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
            self.stream.close()
            self.stream = None


def local_request(state, route, method="GET", timeout=2):
    # Local IPC must bypass system/environment proxy settings.
    port = state["port"]
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid local service port")
    request = Request("http://127.0.0.1:{}{}".format(port, route),
                      headers={"X-0nbb-Token": state["token"]}, method=method)
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def existing_instance(root):
    try:
        state = json.loads((root / ".run" / "state.json").read_text(encoding="utf-8"))
        if state["application"] != APP_ID or state["root"] != str(root.resolve()):
            return None
        answer = local_request(state, "/api/instance")
        if answer["root"] == state["root"] and answer["token"] == state["token"]:
            return answer
    except (OSError, ValueError, KeyError, TypeError, URLError):
        pass
    return None


def write_state(root, state):
    path = root / ".run" / "state.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def control_handler(state, stop_event, open_window):
    from matching.server import Handler

    class DesktopHandler(Handler):
        def authorized(self):
            provided = self.headers.get("X-0nbb-Token", "")
            if not secrets.compare_digest(provided, state["token"]):
                self._json({"error": "Invalid instance token"}, 403)
                return False
            return True

        def do_GET(self):
            if self.path == "/api/instance":
                if self.authorized():
                    self._json(dict(state))
            else:
                super().do_GET()

        def do_POST(self):
            if self.path not in ("/api/open", "/api/stop"):
                self._json({"error": "Unknown endpoint"}, 404)
                return
            if not self.authorized():
                return
            if self.path == "/api/stop":
                self._json({"status": "stopping"})
                stop_event.set()
            else:
                try:
                    open_window()
                    self._json({"status": "opened"})
                except Exception as exc:
                    LOGGER.exception("Opening the application window failed")
                    self._json({"error": str(exc)}, 500)

    return DesktopHandler


class BrowserJob:
    """Ensure this application's browser child processes exit with its launcher."""
    def __init__(self, process):
        self.handle = None
        if os.name != "nt":
            return
        from ctypes import wintypes
        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", wintypes.DWORD), ("min_working_set", ctypes.c_size_t),
                        ("max_working_set", ctypes.c_size_t), ("active_processes", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]
        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", Counters),
                        ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                        ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if handle and kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) and kernel.AssignProcessToJobObject(handle, int(process._handle)):
            self.handle, self.kernel = handle, kernel
        else:
            if handle:
                kernel.CloseHandle(handle)
            LOGGER.warning("Browser job unavailable: Windows error %s", ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def window_action(pid, close=False):
    if os.name != "nt":
        return
    from ctypes import wintypes
    user = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    def visit(handle, unused):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user.IsWindowVisible(handle):
            if close:
                user.PostMessageW(handle, 0x0010, 0, 0)  # WM_CLOSE
            else:
                user.ShowWindow(handle, 9)
                user.SetForegroundWindow(handle)
        return True
    user.EnumWindows(callback_type(visit), 0)


class BrowserWindow:
    def __init__(self, root):
        self.root = root
        self.process = None
        self.job = None

    def open(self, url):
        if self.process is not None and self.process.poll() is None:
            window_action(self.process.pid)
            return
        executable = self.root / "runtime" / "browser" / "chrome.exe"
        if not executable.is_file():
            raise FileNotFoundError("缺少内置浏览器，请完整复制 runtime 文件夹。")
        run = self.root / ".run"
        environment = os.environ.copy()
        for name, folder in (("TEMP", "temp"), ("TMP", "temp"),
                             ("LOCALAPPDATA", "user/Local"), ("APPDATA", "user/Roaming"),
                             ("USERPROFILE", "user")):
            directory = run / folder
            directory.mkdir(parents=True, exist_ok=True)
            environment[name] = str(directory)
        arguments = [
            str(executable), "--app=" + url, "--lang=zh-CN",
            "--user-data-dir=" + str(run / "browser"),
            "--disk-cache-dir=" + str(run / "browser-cache"),
            "--window-size=1460,1020", "--no-first-run", "--no-default-browser-check",
            "--no-proxy-server", "--disable-extensions", "--disable-default-apps",
            "--disable-background-mode", "--disable-background-networking",
            "--disable-component-update", "--disable-sync", "--disable-breakpad",
            "--disable-crash-reporter", "--metrics-recording-only", "--password-store=basic",
            "--disable-features=MediaRouter,OptimizationHints,OptimizationGuideModelDownloading",
            "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost",
        ]
        with (run / "browser.log").open("ab") as log:
            self.process = subprocess.Popen(
                arguments, cwd=str(self.root), env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.job = BrowserJob(self.process)
        LOGGER.info("Application window started, pid=%s", self.process.pid)

    def close(self):
        if self.process is not None and self.process.poll() is None:
            window_action(self.process.pid, close=True)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if self.job and self.job.handle:
                    self.job.close()
                else:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    LOGGER.warning("Browser did not acknowledge shutdown")
        if self.job:
            self.job.close()


def check_package(root=ROOT):
    from matching import MatchingEngine
    executable = Path(sys.executable).resolve()
    executable.relative_to(root)
    for path in sys.path:
        Path(path).resolve().relative_to(root)
    for name in ("data/catalog.json", "data/topologies.json", "preview/index.html",
                 "preview/app.css", "preview/app.js", "preview/i18n.js", "preview/attachment.js", "preview/attachment.html",
                 "runtime/browser/chrome.exe", APP_ENTRY, "preview/app-icon.svg", "preview/app-icon.ico"):
        if not (root / name).is_file():
            raise FileNotFoundError(name)
    engine = MatchingEngine.from_file(root / "data/catalog.json", root / "data/topologies.json")
    return {"status": "ok", "root": str(root), "python": sys.version.split()[0],
            "executable": str(executable), "module_paths": sys.path,
            "catalog_id": engine.catalog_id, **engine.validate_attachments(),
            "browser": str(root / "runtime/browser/chrome.exe")}


def run_application(root=ROOT, no_browser=False, port=8765):
    from matching import MatchingEngine
    from matching.server import create_server
    root = root.resolve()
    (root / ".run").mkdir(exist_ok=True)
    lock = InstanceLock(root / ".run" / "service.lock")
    if not lock.acquire():
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = existing_instance(root)
            if state:
                if not no_browser:
                    local_request(state, "/api/open", method="POST", timeout=10)
                print("http://127.0.0.1:{}".format(state["port"]), flush=True)
                return 0
            if lock.acquire():
                break
            time.sleep(0.2)
        if lock.stream is None:
            raise RuntimeError("程序正在启动，请稍后重试。详见 .run/launcher.log。")
    server = thread = None
    browser = BrowserWindow(root)
    stop_event = threading.Event()
    state = {"schema_version": 1, "application": APP_ID, "root": str(root),
             "token": secrets.token_hex(32), "pid": os.getpid(), "port": 0,
             "mode": "service" if no_browser else "window"}
    open_lock = threading.Lock()
    def open_window():
        with open_lock:
            browser.open("http://127.0.0.1:{}".format(state["port"]))
            state["mode"], state["browser_pid"] = "window", browser.process.pid
            write_state(root, state)
    try:
        engine = MatchingEngine.from_file(root / "data/catalog.json", root / "data/topologies.json")
        handler = control_handler(state, stop_event, open_window)
        try:
            server = create_server(engine, port=port, handler_class=handler)
        except OSError as exc:
            if port and (exc.errno in (errno.EADDRINUSE, errno.EACCES) or getattr(exc, "winerror", None) in (10013, 10048)):
                server = create_server(engine, port=0, handler_class=handler)
            else:
                raise
        state["port"] = server.server_port
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        write_state(root, state)
        LOGGER.info("Service ready at http://127.0.0.1:%s; root=%s", state["port"], root)
        print("http://127.0.0.1:{}".format(state["port"]), flush=True)
        if not no_browser:
            open_window()
        while not stop_event.wait(0.25):
            if browser.process is not None and browser.process.poll() is not None:
                code = browser.process.returncode
                if code:
                    raise RuntimeError("内置浏览器启动或运行失败（{}），详见 .run/browser.log。".format(code))
                break
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        browser.close()
        if thread is not None and thread.is_alive():
            server.shutdown()
            thread.join(timeout=5)
        if server is not None:
            server.server_close()
        path = root / ".run" / "state.json"
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("token") == state["token"]:
                path.unlink()
        except (OSError, ValueError):
            pass
        lock.release()
        LOGGER.info("Service closed")


def stop_application(root=ROOT):
    state = existing_instance(root)
    if state is None:
        return 0
    local_request(state, "/api/stop", method="POST")
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if existing_instance(root) is None:
            return 0
        time.sleep(0.2)
    raise RuntimeError("程序未能及时关闭，详见 .run/launcher.log。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true", help="Serve without opening a window (for local checks)")
    parser.add_argument("--port", type=int, default=8765, help="Preferred local port; occupied ports fall back automatically")
    parser.add_argument("--stop", action="store_true", help="Stop only the authenticated instance in this folder")
    parser.add_argument("--check", action="store_true", help="Validate bundled paths and all attachment data")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    run = ROOT / ".run"
    run.mkdir(exist_ok=True)
    logging.basicConfig(filename=str(run / "launcher.log"), encoding="utf-8",
                        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if sys.stdout is None or sys.stderr is None:
        stream = (run / "console.log").open("a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = stream
    try:
        if args.check:
            print(json.dumps(check_package(), ensure_ascii=False, indent=2), flush=True)
            return 0
        if args.stop:
            return stop_application()
        return run_application(no_browser=args.no_browser, port=args.port)
    except Exception as exc:
        LOGGER.exception("Application failed")
        message = str(exc) + "\n\n日志位置：" + str(run / "launcher.log")
        print(message, file=sys.stderr, flush=True)
        if os.name == "nt" and not (args.no_browser or args.check):
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
