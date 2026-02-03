#!/usr/bin/env python3
"""Ein kleines Beispielskript: liest GitHub-Repositories des authentifizierten Users (GITHUB_TOKEN)
und schreibt die Ergebnisse in Dateien unter ./output:
 - repos.json (alle Repos als JSON-Liste)
 - <owner>__<repo>.md (pro Repo eine Markdown-Übersicht)
Dependencies: PyGithub (pip install PyGithub)
"""
import os
import sys
import json
from datetime import datetime
from github import Github


def repo_to_dict(r):
    # Einige nützliche Felder sammeln
    try:
        topics = r.get_topics()
    except Exception:
        topics = []
    return {
        "name": r.name,
        "full_name": r.full_name,
        "owner": r.owner.login if r.owner else None,
        "private": r.private,
        "description": r.description,
        "html_url": r.html_url,
        "stargazers_count": r.stargazers_count,
        "forks_count": r.forks_count,
        "open_issues_count": r.open_issues_count,
        "language": r.language,
        "default_branch": getattr(r, "default_branch", None),
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "updated_at": r.updated_at.isoformat() if getattr(r, "updated_at", None) else None,
        "archived": getattr(r, "archived", False),
        "disabled": getattr(r, "disabled", False),
        "topics": topics,
    }


def write_repo_md(rdata, outdir):
    safe_name = f"{rdata['full_name'].replace('/', '__')}"
    path = os.path.join(outdir, safe_name + ".md")
    lines = []
    lines.append(f"# {rdata['full_name']}")
    if rdata.get("description"):
        lines.append("\n" + rdata["description"] + "\n")
    lines.append("\n- URL: " + (rdata.get("html_url") or ""))
    lines.append(f"- Privat: {rdata.get('private')}")
    lines.append(f"- Sterne: {rdata.get('stargazers_count')}")
    lines.append(f"- Forks: {rdata.get('forks_count')}")
    lines.append(f"- Open Issues: {rdata.get('open_issues_count')}")
    lines.append(f"- Sprache: {rdata.get('language')}")
    lines.append(f"- Default Branch: {rdata.get('default_branch')}")
    lines.append(f"- Archiviert: {rdata.get('archived')}")
    if rdata.get("topics"):
        lines.append("- Topics: " + ", ".join(rdata.get("topics", [])))
    if rdata.get("created_at"):
        lines.append(f"- Erstellt: {rdata.get('created_at')}")
    if rdata.get("updated_at"):
        lines.append(f"- Zuletzt aktualisiert: {rdata.get('updated_at')}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main():
    # Prefer token from ~/.proman, otherwise GITHUB_TOKEN env var
    token = None
    prom_file = os.path.expanduser("~/.proman")
    if os.path.exists(prom_file):
        try:
            with open(prom_file, "r", encoding="utf-8") as pf:
                for line in pf:
                    line = line.strip()
                    if not line:
                        continue
                    # allow comment lines and a special CURRENT_DATETIME marker
                    if line.startswith("#"):
                        # check comment content after leading '#'
                        comment = line.lstrip("#").strip()
                        if comment.lower().startswith("current_datetime:"):
                            # extract value after ':' and set as env var if provided
                            parts = comment.split(":", 1)
                            if len(parts) > 1:
                                os.environ.setdefault("CURRENT_DATETIME", parts[1].strip())
                        continue
                    # also allow bare 'current_datetime:' lines (non-comment)
                    if line.lower().startswith("current_datetime:"):
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            os.environ.setdefault("CURRENT_DATETIME", parts[1].strip())
                        continue
                    token = line
        except Exception:
            token = None
    if not token:
        token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Fehler: Bitte setze die Umgebungsvariable GITHUB_TOKEN oder lege ~/.proman mit dem Token an.")
        sys.exit(1)
    gh = Github(token)
    try:
        user = gh.get_user()
        repos = list(user.get_repos())
    except Exception as e:
        print("GitHub-Fehler:", e)
        sys.exit(1)
    outdir = os.path.join(os.getcwd(), "output")
    os.makedirs(outdir, exist_ok=True)
    repos_data = []
    for r in repos:
        rd = repo_to_dict(r)
        repos_data.append(rd)
        write_repo_md(rd, outdir)
    result = {
        "generated_at": os.getenv("CURRENT_DATETIME") or (datetime.utcnow().isoformat() + "Z"),
        "user": getattr(user, "login", None),
        "count": len(repos_data),
        "repos": repos_data,
    }
    json_path = os.path.join(outdir, "repos.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Erzeugt: {json_path} und {len(repos_data)} Markdown-Dateien in {outdir}")


if __name__ == '__main__':
    main()
