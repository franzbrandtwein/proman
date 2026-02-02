#!/usr/bin/env python3
"""\nKleine TUI, die list_repos_to_files.py als Modul verwendet und Repos in einem Menü anzeigt.
Benötigt PyGithub installiert (pip install PyGithub) — falls uv benutzt wird: uv run pip install PyGithub
"""
import os
import sys
import curses
import textwrap
import time
from datetime import datetime
import subprocess

try:
    import list_repos_to_files as lrf
except Exception:
    # importing as module should work if file is in same directory
    import importlib.util
    spec = importlib.util.spec_from_file_location("list_repos_to_files", os.path.join(os.path.dirname(__file__), "list_repos_to_files.py"))
    lrf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lrf)

try:
    from github import Github
except Exception as e:
    print("Fehler: PyGithub (github) nicht importierbar:", e)
    print("Bitte installieren: uv run pip install PyGithub")
    sys.exit(1)


def get_token():
    token = None
    prom_file = os.path.expanduser("~/.proman")
    if os.path.exists(prom_file):
        try:
            with open(prom_file, "r", encoding="utf-8") as pf:
                for line in pf:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        continue
                    if line.lower().startswith("current_datetime:"):
                        continue
                    token = line
                    break
        except Exception:
            token = None
    if not token:
        token = os.getenv("GITHUB_TOKEN")
    return token


def fetch_repos(token):
    gh = Github(token)
    user = gh.get_user()
    repos = list(user.get_repos())
    return user, repos


def fetch_repos_progress(stdscr, token):
    """Lädt Repositories mit einer einfachen Fortschrittsanzeige in der curses-Oberfläche."""
    gh = Github(token)
    user = gh.get_user()
    pag = user.get_repos()
    repos = []
    total = getattr(pag, 'totalCount', None) or getattr(pag, 'total_count', None)
    spinner = "|/-\\"
    i = 0
    h, w = stdscr.getmaxyx()
    msg_row = max(0, h // 2)
    # initial message
    stdscr.clear()
    stdscr.addstr(msg_row, 0, "Lade Repositories..."[: w - 1])
    stdscr.refresh()
    for r in pag:
        repos.append(r)
        i += 1
        s = spinner[i % len(spinner)]
        if total:
            text = f"Lade Repos: {i}/{total} {s}"
        else:
            text = f"Lade Repos: {i} {s}"
        stdscr.addstr(msg_row, 0, text.ljust(w - 1)[: w - 1])
        stdscr.refresh()
        time.sleep(0.05)
    # finished
    finished = f"Laden abgeschlossen. Gefundene Repos: {len(repos)}"
    stdscr.addstr(msg_row, 0, finished[: w - 1])
    stdscr.refresh()
    time.sleep(0.2)
    stdscr.clear()
    stdscr.refresh()
    return user, repos


def build_repo_dicts_progress(stdscr, repos):
    """Erstellt Repo-Dicts mit Fortschrittsanzeige während der Verarbeitung.
    Prüft für jedes Repo, ob ein lokales Verzeichnis ~/projekte/<name> existiert und
    protokolliert den Vergleich nach ~/logs/proman.log.
    """
    repos_data = []
    try:
        total = len(repos)
    except Exception:
        total = None
    spinner = "|/-\\"
    h, w = stdscr.getmaxyx()
    msg_row = max(0, h // 2 + 1)

    logdir = os.path.expanduser("~/logs")
    try:
        os.makedirs(logdir, exist_ok=True)
    except Exception:
        logdir = None
    logfile = os.path.join(logdir, "proman.log") if logdir else None

    for i, r in enumerate(repos, start=1):
        rd = lrf.repo_to_dict(r)
        # Prüfen, ob lokal geklont ist (~/projekte/<repo_name>)
        repo_name = rd.get('name') or rd.get('full_name')
        local_path = os.path.expanduser(f"~/projekte/{repo_name}")
        cloned = os.path.exists(local_path)
        rd['cloned'] = cloned
        # Loggen
        ts = os.getenv("CURRENT_DATETIME") or (datetime.utcnow().isoformat() + "Z")
        if logfile:
            try:
                with open(logfile, "a", encoding="utf-8") as lf:
                    lf.write(f"{ts} compare repo={rd.get('full_name')} local_path={local_path} exists={cloned}\n")
            except Exception:
                pass

        repos_data.append(rd)
        s = spinner[i % len(spinner)]
        if total:
            text = f"Verarbeite Repos: {i}/{total} {s}"
        else:
            text = f"Verarbeite Repos: {i} {s}"
        stdscr.addstr(msg_row, 0, text.ljust(w - 1)[: w - 1])
        stdscr.refresh()
    stdscr.addstr(msg_row, 0, (f"Verarbeitung abgeschlossen. Repos verarbeitet: {len(repos_data)}")[: w - 1])
    stdscr.refresh()
    time.sleep(0.2)
    stdscr.clear()
    stdscr.refresh()
    return repos_data


def prompt_input(stdscr, prompt):
    """Zeigt eine Eingabezeile am unteren Rand und liest eine Zeile ein."""
    curses.echo()
    curses.curs_set(1)
    h, w = stdscr.getmaxyx()
    stdscr.addstr(h - 1, 0, " " * (w - 1))
    stdscr.addstr(h - 1, 0, prompt[: w - 1])
    stdscr.refresh()
    try:
        s = stdscr.getstr(h - 1, len(prompt), 200)
        if isinstance(s, bytes):
            s = s.decode("utf-8", "ignore")
    finally:
        curses.noecho()
        curses.curs_set(0)
    return s.strip()


def create_repo_flow(stdscr, token):
    """Interaktiver Dialog zum Erstellen eines neuen Repositories."""
    name = prompt_input(stdscr, "Name des neuen Repos (leer = Abbruch): ")
    if not name:
        return False, "Abgebrochen"
    desc = prompt_input(stdscr, "Beschreibung (optional): ")
    priv = prompt_input(stdscr, "Privat? (y/N): ")
    is_private = True if priv and priv.lower().startswith("y") else False
    try:
        gh = Github(token)
        user = gh.get_user()
        user.create_repo(name, description=desc or "", private=is_private)
        return True, f"Repo '{name}' erstellt"
    except Exception as e:
        return False, str(e)


def draw_menu(stdscr, repos_data, selected_idx, title):
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(0, 0, title[: w - 1])
    for i, r in enumerate(repos_data):
        if i >= h - 2:
            break
        name = f"{r.get('name', r.get('full_name'))}"[: w - 1]
        is_cloned = bool(r.get('cloned'))
        if i == selected_idx:
            attrs = curses.A_REVERSE
            if is_cloned and curses.has_colors():
                attrs |= curses.color_pair(1)
            stdscr.attron(attrs)
            stdscr.addstr(i + 1, 0, name)
            stdscr.attroff(attrs)
        else:
            if is_cloned and curses.has_colors():
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(i + 1, 0, name)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(i + 1, 0, name)
    stdscr.refresh()


def show_details(stdscr, rdata, token):
    # interaktive Detailansicht mit Optionen zum Löschen und Bearbeiten
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        lines = []
        lines.append(rdata.get('name', rdata.get('full_name', '')))
        if rdata.get('description'):
            lines += textwrap.wrap(rdata.get('description'), width=w - 1)
        lines.append(f"URL: {rdata.get('html_url')}")
        lines.append(f"Sterne: {rdata.get('stargazers_count')}  Forks: {rdata.get('forks_count')}")
        lines.append(f"Sprache: {rdata.get('language')}  Privat: {rdata.get('private')}")
        if rdata.get('topics'):
            lines.append("Topics: " + ", ".join(rdata.get('topics')))
        if rdata.get('created_at'):
            lines.append(f"Erstellt: {rdata.get('created_at')}")
        if rdata.get('updated_at'):
            lines.append(f"Aktualisiert: {rdata.get('updated_at')}")

        y = 0
        for ln in lines:
            if y >= h - 3:
                break
            stdscr.addstr(y, 0, str(ln)[: w - 1])
            y += 1

        stdscr.addstr(h - 3, 0, "d: Löschen  e: Bearbeiten  l: Klonen  b: Zurück")
        stdscr.addstr(h - 2, 0, "q: Beenden")
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('d'):
            confirm = prompt_input(stdscr, f"Löschen '{rdata.get('name')}' bestätigen? (y/N): ")
            if confirm and confirm.lower().startswith('y'):
                try:
                    gh = Github(token)
                    full = rdata.get('full_name') or f"{rdata.get('owner')}/{rdata.get('name')}"
                    repo = gh.get_repo(full)
                    repo.delete()
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"Repo '{rdata.get('name')}' gelöscht.")
                    stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                    stdscr.refresh()
                    stdscr.getch()
                    return True
                except Exception as e:
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"Fehler beim Löschen: {e}")
                    stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                    stdscr.refresh()
                    stdscr.getch()
                    continue
            else:
                continue
        elif key == ord('e'):
            new_name = prompt_input(stdscr, f"Neuer Name [{rdata.get('name')}]: ")
            if not new_name:
                new_name = rdata.get('name')
            new_desc = prompt_input(stdscr, f"Beschreibung [{rdata.get('description') or ''}]: ")
            priv = prompt_input(stdscr, f"Privat? (y/N) [{ 'Y' if rdata.get('private') else 'N' }]: ")
            if priv:
                is_private = True if priv.lower().startswith('y') else False
            else:
                is_private = rdata.get('private')
            try:
                gh = Github(token)
                user = gh.get_user()
                repo = user.get_repo(rdata.get('name'))
                repo.edit(name=new_name, description=new_desc or None, private=is_private)
                stdscr.clear()
                stdscr.addstr(0, 0, "Repository bearbeitet.")
                stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                stdscr.refresh()
                stdscr.getch()
                return True
            except Exception as e:
                stdscr.clear()
                stdscr.addstr(0, 0, f"Fehler beim Bearbeiten: {e}")
                stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                stdscr.refresh()
                stdscr.getch()
                continue
        elif key == ord('l'):
            # Klonen nach ~/projekte/<repo_name> falls nicht vorhanden
            repo_name = rdata.get('name') or rdata.get('full_name')
            local_path = os.path.expanduser(f"~/projekte/{repo_name}")
            if os.path.exists(local_path):
                stdscr.clear()
                stdscr.addstr(0, 0, f"Lokaler Pfad existiert bereits: {local_path}")
                stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                stdscr.refresh()
                stdscr.getch()
                continue
            # ensure parent dir
            try:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
            except Exception:
                pass
            stdscr.clear()
            stdscr.addstr(0, 0, f"Klonen nach {local_path} ...")
            stdscr.refresh()
            try:
                res = subprocess.run(["git", "clone", rdata.get('html_url'), local_path], capture_output=True, text=True)
                if res.returncode == 0:
                    # log
                    logdir = os.path.expanduser("~/logs")
                    logfile = os.path.join(logdir, "proman.log") if logdir else None
                    ts = os.getenv("CURRENT_DATETIME") or (datetime.utcnow().isoformat() + "Z")
                    if logfile:
                        try:
                            with open(logfile, "a", encoding="utf-8") as lf:
                                lf.write(f"{ts} clone repo={rdata.get('full_name')} local_path={local_path} success=True\n")
                        except Exception:
                            pass
                    rdata['cloned'] = True
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"Klonen erfolgreich: {local_path}")
                    stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                    stdscr.refresh()
                    stdscr.getch()
                    return True
                else:
                    err = res.stderr or res.stdout
                    stdscr.clear()
                    stdscr.addstr(0, 0, f"Fehler beim Klonen: {err}"[: stdscr.getmaxyx()[1]-1])
                    stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                    stdscr.refresh()
                    stdscr.getch()
                    # log failure
                    logdir = os.path.expanduser("~/logs")
                    logfile = os.path.join(logdir, "proman.log") if logdir else None
                    ts = os.getenv("CURRENT_DATETIME") or (datetime.utcnow().isoformat() + "Z")
                    if logfile:
                        try:
                            with open(logfile, "a", encoding="utf-8") as lf:
                                lf.write(f"{ts} clone repo={rdata.get('full_name')} local_path={local_path} success=False error={err}\n")
                        except Exception:
                            pass
                    continue
            except Exception as e:
                stdscr.clear()
                stdscr.addstr(0, 0, f"Fehler beim Klonen: {e}")
                stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
                stdscr.refresh()
                stdscr.getch()
                continue
        elif key in (ord('b'), ord('q'), 27):
            return False
        else:
            continue


def main_curses(stdscr, token):
    curses.curs_set(0)
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
        except Exception:
            pass
        curses.init_pair(1, curses.COLOR_GREEN, -1)
    stdscr.nodelay(False)
    try:
        user, repos = fetch_repos_progress(stdscr, token)
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Fehler beim Abfragen der Repos: {e}")
        stdscr.addstr(1, 0, "Beende mit beliebiger Taste.")
        stdscr.refresh()
        stdscr.getch()
        return

    repos_data = build_repo_dicts_progress(stdscr, repos)
    selected = 0
    title = f"Repos von {getattr(user, 'login', '')} - q zum Beenden, r zum Neu-Laden, c: Neues Repo"

    while True:
        draw_menu(stdscr, repos_data, selected, title)
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = min(len(repos_data) - 1, selected + 1)
        elif key in (10, 13):  # Enter
            should_reload = show_details(stdscr, repos_data[selected], token)
            if should_reload:
                try:
                    user, repos = fetch_repos_progress(stdscr, token)
                    repos_data = build_repo_dicts_progress(stdscr, repos)
                    selected = 0
                    title = f"Repos von {getattr(user, 'login', '')} - q zum Beenden, r zum Neu-Laden, c: Neues Repo"
                except Exception as e:
                    stdscr.addstr(0, 0, f"Fehler beim Neuladen: {e}")
                    stdscr.getch()
        elif key in (ord('q'), 27):
            break
        elif key == ord('c'):
            ok, msg = create_repo_flow(stdscr, token)
            stdscr.clear()
            stdscr.addstr(0, 0, msg[: stdscr.getmaxyx()[1]-1])
            stdscr.addstr(1, 0, "Beliebige Taste zum Fortfahren.")
            stdscr.refresh()
            stdscr.getch()
            try:
                user, repos = fetch_repos_progress(stdscr, token)
                repos_data = build_repo_dicts_progress(stdscr, repos)
                selected = 0
                title = f"Repos von {getattr(user, 'login', '')} - q zum Beenden, r zum Neu-Laden, c: Neues Repo"
            except Exception as e:
                stdscr.addstr(0, 0, f"Fehler beim Neuladen: {e}")
                stdscr.getch()
        elif key == ord('r'):
            try:
                user, repos = fetch_repos_progress(stdscr, token)
                repos_data = build_repo_dicts_progress(stdscr, repos)
                selected = 0
                title = f"Repos von {getattr(user, 'login', '')} - q zum Beenden, r zum Neu-Laden, c: Neues Repo"
            except Exception as e:
                stdscr.addstr(0, 0, f"Fehler beim Neuladen: {e}")
                stdscr.getch()


def main():
    token = get_token()
    if not token:
        print("Kein GITHUB_TOKEN gefunden. Bitte setzen oder ~/.proman anlegen.")
        sys.exit(1)
    curses.wrapper(main_curses, token)


if __name__ == '__main__':
    main()
