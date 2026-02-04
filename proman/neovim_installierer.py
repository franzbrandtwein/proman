"""neovim_installierer

Kleines Hilfsmodul, um Neovim im Userspace zu installieren (Linux).

Funktionen:
- is_nvim_installed() -> bool
- install_appimage(prefix='~/.local') -> str  # Pfad zur installierten nvim
- ensure_nvim(prefix='~/.local') -> str  # installiert falls nötig und gibt Pfad zurück

Das Modul lädt die offizielle nvim.appimage von GitHubs Releases (latest) herunter
und legt sie unter <prefix>/bin/nvim ab (macht ausführbar).
"""
from __future__ import annotations

import os
import sys
import stat
import shutil
import urllib.request
import urllib.error
import json
import tarfile
import tempfile
import platform
from datetime import datetime
from typing import Optional


APPIMAGE_LATEST_URL = "https://github.com/neovim/neovim/releases/latest/download/nvim.appimage"


def _get_latest_asset() -> dict:
    """Query GitHub API for the latest neovim release and return a suitable asset URL and kind.

    Returns a dict: {"url": <browser_download_url>, "kind": "appimage"|"tarball"}
    """
    api = "https://api.github.com/repos/neovim/neovim/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "proman-neovim-installierer"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
    except Exception as e:
        raise RuntimeError(f"Fehler beim Abfragen der GitHub Releases API: {e}")

    assets = data.get("assets", []) or []
    arch = platform.machine().lower()
    arch_aliases = []
    if arch in ("x86_64", "amd64"):
        arch_aliases = ["x86_64", "linux64", "amd64", "x86-64"]
    elif arch in ("aarch64", "arm64"):
        arch_aliases = ["aarch64", "arm64"]
    else:
        arch_aliases = [arch]

    # Prefer AppImage when available
    for a in assets:
        name = (a.get("name") or "").lower()
        url = a.get("browser_download_url")
        if not url:
            continue
        if "appimage" in name:
            # accept regardless of arch tag; AppImage often is portable
            return {"url": url, "kind": "appimage"}

    # Prefer tarball matching architecture
    for a in assets:
        name = (a.get("name") or "").lower()
        url = a.get("browser_download_url")
        if not url:
            continue
        if any(ext in name for ext in ["tar.gz", "tar.xz", "tar.bz2"]):
            if any(k in name for k in arch_aliases) or "linux" in name:
                return {"url": url, "kind": "tarball"}

    # fallback to static appimage url
    return {"url": APPIMAGE_LATEST_URL, "kind": "appimage"}


def is_nvim_installed() -> bool:
    """Prüft, ob 'nvim' im PATH vorhanden ist oder in ~/.local/bin/nvim."""
    if shutil.which("nvim"):
        return True
    local = os.path.expanduser("~/.local/bin/nvim")
    return os.path.exists(local) and os.access(local, os.X_OK)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def install_appimage(prefix: str = "~/.local", url: Optional[str] = None) -> str:
    """Lädt nvim.appimage herunter und installiert sie nach <prefix>/bin/nvim.

    Gibt den Pfad zur installierten nvim zurück.
    Erhältlich nur unter Linux (AppImage).
    """
    if sys.platform != "linux" and not sys.platform.startswith("linux"):
        raise NotImplementedError("install_appimage ist nur unter Linux unterstützt")

    if url is None:
        info = _get_latest_asset()
        url = info.get('url')
        kind = info.get('kind')
    else:
        kind = 'appimage'

    prefix = os.path.expanduser(prefix)
    bin_dir = os.path.join(prefix, "bin")
    _ensure_dir(bin_dir)
    target = os.path.join(bin_dir, "nvim")

    # If target already exists and is executable, simply return
    if os.path.exists(target) and os.access(target, os.X_OK):
        return target

    # Download to a temporary file in the bin_dir
    tmp_path = target + ".download"

    # Log the chosen download URL for debugging
    try:
        logdir = os.path.expanduser("~/.local/share/proman")
        os.makedirs(logdir, exist_ok=True)
        logfile = os.path.join(logdir, "neovim_install.log")
        ts = datetime.utcnow().isoformat() + "Z"
        with open(logfile, "a", encoding="utf-8") as lf:
            lf.write(f"{ts} download_url={url} kind={kind}\n")
    except Exception:
        # non-fatal logging failure
        pass

    # also emit to stdout for immediate visibility
    try:
        print(f"Downloading neovim from {url} (kind={kind})")
    except Exception:
        pass

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "proman-neovim-installierer"})
        with urllib.request.urlopen(req) as resp, open(tmp_path, "wb") as out:
            shutil.copyfileobj(resp, out)
    except urllib.error.HTTPError as e:
        # cleanup
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Fehler beim Herunterladen von nvim.appimage: HTTP {e.code} {e.reason} url={url}")
    except Exception as e:
        # cleanup
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Fehler beim Herunterladen von nvim.appimage: {e}")

    # If downloaded tarball, extract nvim binary
    if kind == 'tarball':
        tmpdir = tempfile.mkdtemp(prefix='nvim_extract_')
        try:
            try:
                with tarfile.open(tmp_path) as tf:
                    tf.extractall(path=tmpdir)
            except Exception as e:
                raise RuntimeError(f"Fehler beim Entpacken des Tarballs: {e}")
            # search for bin/nvim
            nvim_src = None
            for root, dirs, files in os.walk(tmpdir):
                if 'nvim' in files and os.path.basename(root) == 'bin':
                    nvim_src = os.path.join(root, 'nvim')
                    break
            if not nvim_src:
                # try common path
                for root, dirs, files in os.walk(tmpdir):
                    if 'nvim' in files:
                        possible = os.path.join(root, 'nvim')
                        # check ELF
                        try:
                            if os.path.getsize(possible) > 0:
                                nvim_src = possible
                                break
                        except Exception:
                            continue
            if not nvim_src or not os.path.exists(nvim_src):
                raise RuntimeError("Konnte nvim-Binärdatei im heruntergeladenen Tarball nicht finden")
            # move to target
            os.replace(nvim_src, target)
            st = os.stat(target)
            os.chmod(target, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        finally:
            # cleanup
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            try:
                shutil.rmtree(tmpdir)
            except Exception:
                pass
        return target

    # Make executable and move into place
    try:
        st = os.stat(tmp_path)
        os.chmod(tmp_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        # atomic move
        os.replace(tmp_path, target)
    except Exception as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Fehler beim Installieren von nvim: {e}")

    return target


def ensure_nvim(prefix: str = "~/.local") -> str:
    """Stellt sicher, dass nvim verfügbar ist; installiert falls nötig in Userspace und
    gibt den Pfad zur ausführbaren nvim zurück.
    """
    # prefer system nvim if available
    which = shutil.which("nvim")
    if which:
        return which
    installed = install_appimage(prefix=prefix)
    return installed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Install nvim appimage into user space (~/.local/bin)")
    parser.add_argument("--prefix", default="~/.local", help="Installations-Prefix (default: ~/.local)")
    parser.add_argument("--force", action="store_true", help="Force download even if target exists and is executable")
    args = parser.parse_args()

    try:
        if args.force and os.path.exists(os.path.expanduser(os.path.join(args.prefix, "bin", "nvim"))):
            try:
                os.remove(os.path.expanduser(os.path.join(args.prefix, "bin", "nvim")))
            except Exception:
                pass
        path = ensure_nvim(prefix=args.prefix)
        print(path)
    except Exception as e:
        print("Fehler:", e, file=sys.stderr)
        sys.exit(1)
