"""Assemble the local Windows runtime from existing, verified binaries.

Only the packaging step reads its --python-source and --browser-source.
The resulting application uses relative paths and needs neither source.
"""
import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assemble(python_source, browser_source, browser_version):
    destination = ROOT / "runtime"
    python_target = destination / "python"
    browser_target = destination / "browser"
    python_target.mkdir(parents=True, exist_ok=True)
    browser_target.mkdir(parents=True, exist_ok=True)
    dll_name = next(python_source.glob("python3[0-9][0-9].dll")).name
    version_tag = dll_name[:-4]
    for name in ("python.exe", "pythonw.exe", "python3.dll", dll_name,
                 "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        shutil.copy2(python_source / name, python_target / name)
    extensions = python_target / "DLLs"
    extensions.mkdir(exist_ok=True)
    for path in (python_source / "DLLs").iterdir():
        if path.suffix.lower() in (".pyd", ".dll") and not path.name.startswith(("_test", "_ctypes_test", "_tkinter", "tcl", "tk")):
            shutil.copy2(path, extensions / path.name)
    excluded = {"site-packages", "__pycache__", "test", "tests",
                "idlelib", "turtledemo", "ensurepip", "tkinter"}
    zip_target = python_target / (version_tag + ".zip")
    count = 0
    with zipfile.ZipFile(zip_target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted((python_source / "Lib").rglob("*")):
            relative = path.relative_to(python_source / "Lib")
            if path.is_file() and not excluded.intersection(relative.parts) and path.suffix in (".py", ".txt"):
                archive.write(path, relative.as_posix())
                count += 1
    (python_target / (version_tag + "._pth")).write_text(
        "# Isolated, relocatable application runtime; never import site.\n"
        + version_tag + ".zip\nDLLs\n.\n..\\..\\\n", encoding="ascii")
    shutil.copy2(browser_source / "chrome.exe", browser_target / "chrome.exe")
    version_target = browser_target / browser_version
    version_target.mkdir(exist_ok=True)
    version_source = browser_source / browser_version
    for path in version_source.iterdir():
        if path.is_file():
            shutil.copy2(path, version_target / path.name)
    locales = version_target / "Locales"
    locales.mkdir(exist_ok=True)
    for locale in ("en-US.pak", "zh-CN.pak"):
        shutil.copy2(version_source / "Locales" / locale, locales / locale)
    for dirname in ("IwaKeyDistribution", "MEIPreload", "PrivacySandboxAttestationsPreloaded"):
        if (version_source / dirname).is_dir():
            shutil.copytree(version_source / dirname, version_target / dirname, dirs_exist_ok=True)
    manifest = {
        "schema_version": 1, "platform": "Windows x64",
        "python_version": sys.version.split()[0],
        "python_entry": "runtime/python/pythonw.exe",
        "python_stdlib_file_count": count,
        "browser_version": browser_version,
        "browser_entry": "runtime/browser/chrome.exe",
        "browser_notices": "chrome://credits (available inside the bundled browser)",
        "files": [
            {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size,
             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted(destination.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        ],
    }
    application_names = [
        "launcher.py", "0νββ 模型探索.exe",
        "data/catalog.json", "data/topologies.json", "data/template_normalization.json",
        "preview/index.html", "preview/attachment.html", "preview/app.css", "preview/app.js", "preview/i18n.js", "preview/attachment.js",
        "preview/app-icon.svg", "preview/app-icon.ico",
    ]
    application_names += [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "matching").glob("*.py"))]
    manifest["application_files"] = [
        {"path": name, "size": (ROOT / name).stat().st_size,
         "sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest()}
        for name in application_names if (ROOT / name).is_file()
    ]
    manifest["application_name"] = "0νββ Model Explorer"
    manifest["application_entry"] = "0νββ 模型探索.exe"
    manifest["application_icon"] = "preview/app-icon.ico"
    manifest["system_requirements"] = "Windows x64; operating-system components and fonts only"
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"runtime_files": len(manifest["files"]),
                      "runtime_bytes": sum(item["size"] for item in manifest["files"]),
                      "stdlib_files": count, "python": manifest["python_version"],
                      "browser": browser_version}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python-source", type=Path, required=True)
    parser.add_argument("--browser-source", type=Path, required=True)
    parser.add_argument("--browser-version", required=True)
    args = parser.parse_args()
    assemble(args.python_source, args.browser_source, args.browser_version)
