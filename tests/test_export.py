#!/usr/bin/env python3
"""Mermaid export: `vers_mermaid` must produce a valid erDiagram that parses
back to the same tables. Round-trips the committed examples (SQL → Mermaid →
parse) and checks the table count survives. Exits non-zero on a mismatch."""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)

EXEMPLES = ['mediatheque', 'chinook', 'northwind', 'pagila']


def principal():
    echecs = []
    for nom in EXEMPLES:
        tables, fks = mcdview.analyser_sql(str(RACINE / 'exemples' / f'{nom}.sql'))
        mmd = mcdview.vers_mermaid(tables, fks)
        if not mmd.startswith('erDiagram'):
            echecs.append(f'{nom}: la sortie ne commence pas par erDiagram')
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'x.mmd'
            p.write_text(mmd)
            rt, rf = mcdview.analyser_mermaid(str(p))
        # every table must survive the round-trip (FKs may merge: one Mermaid
        # relationship per table pair, so a double FK collapses — expected)
        if len(rt) != len(tables):
            echecs.append(f'{nom}: {len(rt)} tables après round-trip != {len(tables)}')
        print(f'{"FAIL" if any(nom in e for e in echecs) else "ok  "} {nom}: '
              f'{len(tables)} tables → Mermaid → {len(rt)} tables, {len(rf)} FKs')
    # the CLI flag prints the erDiagram to stdout
    r = subprocess.run(
        [sys.executable, str(RACINE / 'mcdview.py'),
         str(RACINE / 'exemples' / 'chinook.sql'), '--to-mermaid'],
        capture_output=True, text=True)
    if r.returncode or not r.stdout.startswith('erDiagram'):
        echecs.append(f'--to-mermaid CLI: sortie inattendue ({r.stdout[:40]!r})')

    if echecs:
        print('\nÉCHECS export Mermaid :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('\nexport Mermaid : erDiagram valide (fonction + CLI), round-trip OK')


if __name__ == '__main__':
    principal()
