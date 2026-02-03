"""Utilities to install/update Neovim plugins from git repos.

The module installs plugins into the 'pack' directory used by Neovim:
~/.local/share/nvim/site/pack/<pack_name>/start/<plugin_name>

Functions:
- get_pack_start_dir(pack_name='proman') -> str
- install_plugin(repo_url, name=None, pack_name='proman', dest_dir=None, rev=None, update=False) -> str
- list_installed(pack_name='proman') -> list[str]

Behavior:
- If a plugin directory already exists and update=False, installation is skipped.
- If update=True and the directory is a git repo, a 'git pull' is attempted.
- If rev is provided, a checkout to the given ref is attempted after clone.

Requires git available on PATH.
"""
from __future__ import annotations

import os
import subprocess
import shlex
import shutil
from typing import List, Optional


def get_pack_start_dir(pack_name: str = "proman") -> str:
    """Return the Neovim "pack/*/start" dir for given pack_name, creating it if needed."""
    base = os.path.expanduser("~/.local/share/nvim/site/pack")
    start = os.path.join(base, pack_name, "start")
    os.makedirs(start, exist_ok=True)
    return start


def _run_git(args: List[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git"] + args
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)


def _repo_name_from_url(url: str) -> str:
    # strip trailing .git and path
    name = url.rstrip('/').split('/')[-1]
    if name.endswith('.git'):
        name = name[:-4]
    return name


def install_plugin(repo_url: str, name: Optional[str] = None, pack_name: str = "proman", dest_dir: Optional[str] = None, rev: Optional[str] = None, update: bool = False) -> str:
    """Install or update a plugin from repo_url.

    Returns the path where the plugin is installed.
    Raises RuntimeError on failure.
    """
    if not name:
        name = _repo_name_from_url(repo_url)
    if dest_dir:
        target = os.path.abspath(dest_dir)
    else:
        start_dir = get_pack_start_dir(pack_name)
        target = os.path.join(start_dir, name)

    # If target exists
    if os.path.exists(target):
        # If update requested and it's a git repo -> git pull
        git_dir = os.path.join(target, '.git')
        if update and os.path.isdir(git_dir):
            try:
                _run_git(['fetch', '--all'], cwd=target)
                _run_git(['pull'], cwd=target)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to update plugin at {target}: {e.stderr}")
            # optionally checkout rev
            if rev:
                try:
                    _run_git(['checkout', rev], cwd=target)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to checkout {rev} in {target}: {e.stderr}")
            return target
        else:
            # skip installation
            return target

    # Clone into target
    try:
        _run_git(['clone', repo_url, target])
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git clone failed: {e.stderr}")

    # If revision provided, checkout
    if rev:
        try:
            _run_git(['checkout', rev], cwd=target)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to checkout {rev} in {target}: {e.stderr}")

    return target


def list_installed(pack_name: str = "proman") -> List[str]:
    start_dir = get_pack_start_dir(pack_name)
    try:
        return sorted([d for d in os.listdir(start_dir) if os.path.isdir(os.path.join(start_dir, d))])
    except FileNotFoundError:
        return []


def remove_plugin(name: str, pack_name: str = "proman", ignore_missing: bool = False) -> bool:
    """Remove a plugin directory by name from the given pack.

    Returns True if removed, False if not found and ignore_missing is True.
    Raises RuntimeError on failure to remove.
    """
    start_dir = get_pack_start_dir(pack_name)
    target = os.path.join(start_dir, name)
    target_abs = os.path.abspath(target)
    start_abs = os.path.abspath(start_dir)

    # Safety: ensure target is inside start_dir
    if not (target_abs == start_abs or target_abs.startswith(start_abs + os.sep)):
        raise RuntimeError(f"Refusing to remove path outside pack start dir: {target_abs}")

    if not os.path.exists(target_abs):
        if ignore_missing:
            return False
        raise FileNotFoundError(f"Plugin not found: {target}")

    try:
        shutil.rmtree(target_abs)
    except Exception as e:
        raise RuntimeError(f"Failed to remove plugin {name}: {e}")

    return True
