"""neovim_cli

Konsolenwerkzeug, um Funktionen aus neovim_commander, neovim_installierer und nvim_plugins aufzurufen.

Beispiele:
  python -m proman.neovim_cli start-server --address /tmp/nvim.sock
  python -m proman.neovim_cli open-files --address /tmp/nvim.sock /path/to/dir
  python -m proman.neovim_cli ensure-nvim
  python -m proman.neovim_cli install-plugin https://github.com/owner/repo.git
"""
from __future__ import annotations

import sys
import argparse
from typing import List, Optional

from . import neovim_commander as commander
from . import neovim_installierer as installer
from . import nvim_plugins as plugins


def cmd_start_server(args: argparse.Namespace) -> int:
    try:
        proc, addr = commander.start_server(address=args.address, headless=not args.gui)
        print(f"started pid={getattr(proc, 'pid', None)} address={addr}")
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def cmd_open_files(args: argparse.Namespace) -> int:
    try:
        commander.open_files(args.address, args.files, use_tabs=args.tabs)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 3


def cmd_ensure_nvim(args: argparse.Namespace) -> int:
    try:
        path = installer.ensure_nvim(prefix=args.prefix)
        print(path)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 4


def cmd_install_appimage(args: argparse.Namespace) -> int:
    try:
        path = installer.install_appimage(prefix=args.prefix, url=args.url)
        print(path)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 5


def cmd_is_installed(args: argparse.Namespace) -> int:
    ok = installer.is_nvim_installed()
    print("installed" if ok else "missing")
    return 0 if ok else 6


def cmd_install_plugin(args: argparse.Namespace) -> int:
    try:
        dest = plugins.install_plugin(args.repo, name=args.name, pack_name=args.pack, dest_dir=args.dest, rev=args.rev, update=args.update)
        print(dest)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 7


def cmd_list_plugins(args: argparse.Namespace) -> int:
    try:
        items = plugins.list_installed(pack_name=args.pack)
        for it in items:
            print(it)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 8


def cmd_remove_plugin(args: argparse.Namespace) -> int:
    try:
        ok = plugins.remove_plugin(args.name, pack_name=args.pack, ignore_missing=args.ignore_missing)
        print("removed" if ok else "missing")
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 9


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="neovim_cli")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("start-server", help="Start a neovim server")
    s.add_argument("--address", default=None)
    s.add_argument("--gui", action="store_true", help="Start with gui (no --headless)")
    s.set_defaults(func=cmd_start_server)

    s = sub.add_parser("open-files", help="Open files/paths in existing neovim server")
    s.add_argument("address")
    s.add_argument("files", nargs="+")
    s.add_argument("--tabs", action="store_true")
    s.set_defaults(func=cmd_open_files)

    s = sub.add_parser("ensure-nvim", help="Ensure nvim installed (prefers system) and print path")
    s.add_argument("--prefix", default="~/.local")
    s.set_defaults(func=cmd_ensure_nvim)

    s = sub.add_parser("install-appimage", help="Download and install nvim.appimage into prefix/bin/nvim")
    s.add_argument("--prefix", default="~/.local")
    s.add_argument("--url", default=None)
    s.set_defaults(func=cmd_install_appimage)

    s = sub.add_parser("is-installed", help="Print if nvim is installed")
    s.set_defaults(func=cmd_is_installed)

    s = sub.add_parser("install-plugin", help="Install a Neovim plugin from git")
    s.add_argument("repo")
    s.add_argument("--name")
    s.add_argument("--pack", default="proman")
    s.add_argument("--dest")
    s.add_argument("--rev")
    s.add_argument("--update", action="store_true")
    s.set_defaults(func=cmd_install_plugin)

    s = sub.add_parser("list-plugins", help="List installed plugins")
    s.add_argument("--pack", default="proman")
    s.set_defaults(func=cmd_list_plugins)

    s = sub.add_parser("remove-plugin", help="Remove a plugin by name")
    s.add_argument("name")
    s.add_argument("--pack", default="proman")
    s.add_argument("--ignore-missing", action="store_true")
    s.set_defaults(func=cmd_remove_plugin)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func") or args.func is None:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
