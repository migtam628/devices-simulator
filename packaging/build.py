"""Build portable Devices Simulator executable on the current host OS."""
from __future__ import annotations
import hashlib
import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "DevicesSimulator"
RELEASE = ROOT / "release"


def platform_target():
    system = platform.system()
    arch = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
    names = {"Windows": "Windows", "Darwin": "macOS", "Linux": "Linux"}
    if system not in names:
        raise RuntimeError(f"Unsupported target: {system}")
    return names[system], arch


def package(platform_name, arch):
    RELEASE.mkdir(parents=True, exist_ok=True)
    stem = f"{NAME}-{platform_name}-{arch}"
    dist = ROOT / "dist"
    if platform_name == "macOS":
        bundle = dist / (NAME + ".app")
        assert bundle.is_dir(), f"Missing app bundle: {bundle}"
        target = RELEASE / (stem + ".zip")
        # Preserve app contents, symlinks, executable flags and metadata.
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(bundle), str(target)], check=True)
    elif platform_name == "Windows":
        folder = dist / NAME
        assert (folder / (NAME + ".exe")).is_file(), "Windows EXE missing"
        target = RELEASE / (stem + ".zip")
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    archive.write(path, (Path(NAME) / path.relative_to(folder)).as_posix())
    else:
        folder = dist / NAME
        assert (folder / NAME).is_file(), "Linux executable missing"
        target = RELEASE / (stem + ".tar.gz")
        with tarfile.open(target, "w:gz") as archive:
            archive.add(folder, arcname=NAME)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (RELEASE / (target.name + ".sha256")).write_text(
        f"{checksum}  {target.name}\n", encoding="utf-8"
    )
    print(f"Created: {target} ({target.stat().st_size:,} bytes)")


def main():
    target_os, arch = platform_target()
    delimiter = os.pathsep
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--name", NAME,
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--paths", str(ROOT / "src"),
        "--add-data", f"{ROOT / 'src/lulwa_virtual_printer/ui'}{delimiter}lulwa_virtual_printer/ui",
        "--add-data", f"{ROOT / 'src/lulwa_virtual_printer/ppd'}{delimiter}lulwa_virtual_printer/ppd",
        "--collect-all", "fitz",
        "--hidden-import", "PIL.JpegImagePlugin",
        "--hidden-import", "PIL.PngImagePlugin",
    ]
    if target_os in ("Windows", "macOS"):
        cmd += ["--windowed", "--collect-all", "webview"]
    cmd.append(str(ROOT / "packaging" / "launcher.py"))
    print(f"Packaging {target_os}/{arch}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
    package(target_os, arch)


if __name__ == "__main__":
    main()
