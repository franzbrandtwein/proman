"""Hilfsmethoden zum Lesen von CSV-Daten im Projekt.

Enthält eine Funktion read_nvim_csv(), die daten/nvim.csv liest und die Zeilen
als Liste von dicts zurückliefert.
"""
from __future__ import annotations

import csv
import os
from typing import List, Dict


def read_nvim_csv(path: str = "daten/nvim.csv", encoding: str = "utf-8") -> List[Dict[str, str]]:
    """Liest die CSV-Datei (Standard: daten/nvim.csv relative zum Projektroot)
    und gibt eine Liste von Dictionaries zurück (Spaltenkopf -> Wert).

    Wenn path relativ ist, wird er relativ zum Projekt-Root (Verzeichnis über dem
    proman-Package-Verzeichnis) aufgelöst.
    """
    # Auflösen des Standardpfads relativ zum Projektroot (ein Verzeichnis über diesem Modul)
    if not os.path.isabs(path):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        path = os.path.join(project_root, path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV file not found: {path}")

    rows: List[Dict[str, str]] = []
    with open(path, newline="", encoding=encoding) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Konvertiere OrderedDict in normales dict und entferne führende/trailing spaces
            cleaned = {k.strip(): (v.strip() if v is not None else "") for k, v in row.items()}
            rows.append(cleaned)
    return rows


def install_plugin_from_csv_line(line_number: int, pack_name: str = "proman", rev: Optional[str] = None, update: bool = False) -> str:
    """Installiert das Plugin, das in daten/nvim.csv in der gegebenen Zeile steht.

    line_number ist 1-basiert (erste Datenzeile nach dem Header ist 1).
    Gibt den Pfad zurück, in den das Plugin installiert wurde.
    """
    rows = read_nvim_csv()
    if line_number < 1 or line_number > len(rows):
        raise IndexError(f"line_number {line_number} out of range (1..{len(rows)})")
    row = rows[line_number - 1]

    # Versuche typische Feldnamen für Repo-URL
    candidates = ["repo", "url", "git", "ssh_url", "ssh", "clone_url", "https", "git_url", "clone"]
    repo_url = None
    for c in candidates:
        v = row.get(c)
        if v:
            sv = v.strip()
            if sv.startswith("git@") or sv.startswith("http") or "github.com" in sv:
                repo_url = sv
                break
    if not repo_url:
        # Fallback: suche irgendein Feld mit einer URL-ähnlichen Zeichenkette
        for k, v in row.items():
            if not v:
                continue
            sv = str(v).strip()
            if sv.startswith("git@") or sv.startswith("http") or "github.com" in sv:
                repo_url = sv
                break
    if not repo_url:
        raise RuntimeError(f"Keine Repo-URL in Zeile {line_number} gefunden: {row}")

    # Bestimme optionalen Namen
    name = row.get("name") or row.get("plugin") or None

    # Importiere installer und installiere
    from . import nvim_plugins
    return nvim_plugins.install_plugin(repo_url, name=name, pack_name=pack_name, rev=rev, update=update)
