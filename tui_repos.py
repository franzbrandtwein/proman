#!/usr/bin/env python3
"""\nKleine TUI, die list_repos_to_files.py als Modul verwendet und Repos in einem Menü anzeigt.
Benötigt PyGithub installiert (pip install PyGithub) — falls uv benutzt wird: uv run pip install PyGithub
"""
import os
import sys
import curses
import textwrap

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
        if i == selected_idx:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(i + 1, 0, name)
            stdscr.attroff(curses.A_REVERSE)
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

        stdscr.addstr(h - 3, 0, "d: Löschen  e: Bearbeiten  b: Zurück")
        stdscr.addstr(h - 2, 0, "q: Beenden")
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('d'):
            confirm = prompt_input(stdscr, f"Löschen '{rdata.get('name')}' bestätigen? (y/N): ")
            if confirm and confirm.lower().startswith('y'):
                try:
                    gh = Github(token)
                    user = gh.get_user()
                    user.delete_repo(rdata.get('name'))
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
        elif key in (ord('b'), ord('q'), 27):
            return False
        else:
            continue


def main_curses(stdscr, token):
    curses.curs_set(0)
    stdscr.nodelay(False)
    try:
        user, repos = fetch_repos(token)
    except Exception as e:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Fehler beim Abfragen der Repos: {e}")
        stdscr.addstr(1, 0, "Beende mit beliebiger Taste.")
        stdscr.refresh()
        stdscr.getch()
        return

    repos_data = [lrf.repo_to_dict(r) for r in repos]
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
                    user, repos = fetch_repos(token)
                    repos_data = [lrf.repo_to_dict(r) for r in repos]
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
                user, repos = fetch_repos(token)
                repos_data = [lrf.repo_to_dict(r) for r in repos]
                selected = 0
                title = f"Repos von {getattr(user, 'login', '')} - q zum Beenden, r zum Neu-Laden, c: Neues Repo"
            except Exception as e:
                stdscr.addstr(0, 0, f"Fehler beim Neuladen: {e}")
                stdscr.getch()
        elif key == ord('r'):
            try:
                user, repos = fetch_repos(token)
                repos_data = [lrf.repo_to_dict(r) for r in repos]
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
