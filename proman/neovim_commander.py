"""Ein kleines Hilfsmodul zum Starten eines Neovim-Servers und Öffnen von Dateien.

Funktionen:
- start_server(address=None, headless=True): startet einen nvim-Prozess mit --listen und gibt (proc, address) zurück.
- open_files(address, files, use_tabs=False): öffnet Dateien in einem laufenden Neovim-Server.

Dieses Modul versucht zuerst, 'pynvim' zu verwenden; falls nicht vorhanden, wird versucht, das CLI-Tool 'nvr' (neovim-remote) zu nutzen.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile
import time
from typing import Iterable, Optional, Tuple


def _make_socket_path() -> str:
    # create a reasonably unique UNIX socket path in /tmp
    pid = os.getpid()
    rnd = next(tempfile._get_candidate_names())
    path = f"/tmp/nvim-{pid}-{rnd}.sock"
    return path


def start_server(address: Optional[str] = None, headless: bool = True) -> Tuple[subprocess.Popen, str]:
    """Startet einen Neovim-Server.

    address: optionaler Pfad (UNIX socket) oder Adresse (z.B. "127.0.0.1:6666" mit "tcp:")
    Gibt (Popen-Objekt, address) zurück.
    """
    if address is None:
        address = _make_socket_path()

    cmd = ["nvim"]
    if headless:
        cmd.append("--headless")
    cmd += ["--listen", address]

    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Give nvim a moment to start and create the socket
    time.sleep(0.15)

    return proc, address


def _open_via_pynvim(address: str, files: Iterable[str], use_tabs: bool = False) -> None:
    import pynvim

    # attach to UNIX socket
    nvim = None
    # choose attach method
    try:
        nvim = pynvim.attach('socket', path=address)
    except Exception:
        # try TCP style address if provided as tcp:host:port or host:port
        if address.startswith('tcp:'):
            _, host, port = address.split(':', 2)
            nvim = pynvim.attach('tcp', host=host, port=int(port))
        elif ':' in address:
            host, port = address.split(':', 1)
            nvim = pynvim.attach('tcp', host=host, port=int(port))
        else:
            raise

    try:
        for f in files:
            if use_tabs:
                nvim.command(f"tabedit {shlex.quote(f)}")
            else:
                nvim.command(f"edit {shlex.quote(f)}")
        # bring buffers into view
        nvim.command('redraw!')
    finally:
        try:
            nvim.close()
        except Exception:
            pass


def _open_via_nvr(address: str, files: Iterable[str], use_tabs: bool = False) -> None:
    nvr = shutil.which('nvr')
    if not nvr:
        raise RuntimeError("'nvr' (neovim-remote) not found in PATH; install pynvim or nvr to control a running nvim instance")
    args = [nvr, '--server', address]
    if use_tabs:
        args.append('--remote-tab')
    else:
        args.append('--remote')
    args += list(files)
    subprocess.run(args, check=True)


def open_files(address: str, files: Iterable[str], use_tabs: bool = False) -> None:
    """Öffnet Dateien in einem laufenden Neovim-Server.

    Versucht zuerst, 'pynvim' zu verwenden; fällt auf 'nvr' zurück, falls verfügbar.
    """
    files = list(files)
    if not files:
        return

    # try pynvim
    try:
        import pynvim  # type: ignore
    except Exception:
        pynvim = None

    if pynvim:
        try:
            _open_via_pynvim(address, files, use_tabs=use_tabs)
            return
        except Exception as e:
            # fallback to nvr
            pass

    # try nvr
    try:
        _open_via_nvr(address, files, use_tabs=use_tabs)
        return
    except Exception as e:
        raise RuntimeError(f"Konnte Dateien nicht im Neovim-Server öffnen: {e}")


# Convenience helper: start a server if none exists and open files
def ensure_and_open(files: Iterable[str], address: Optional[str] = None, headless: bool = True, use_tabs: bool = False) -> Tuple[subprocess.Popen, str]:
    """Startet einen Server falls nötig und öffnet Dateien.

    Gibt (proc, address) zurück; proc kann None sein, wenn bereits ein Server lief (not implemented detection).
    """
    proc, addr = start_server(address=address, headless=headless)
    open_files(addr, files, use_tabs=use_tabs)
    return proc, addr
