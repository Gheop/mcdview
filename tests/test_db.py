#!/usr/bin/env python3
"""End-to-end test of `--db`: point mcdview at a live PostgreSQL, let it shell
to pg_dump, and check the generated page carries the schema. Skips (exit 0)
unless MCDVIEW_TEST_DB names a reachable database and psql/pg_dump are present,
so it is a no-op locally; CI runs it against a postgres service container."""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
URL = os.environ.get('MCDVIEW_TEST_DB')

SCHEMA = """
DROP TABLE IF EXISTS ligne, commande, client CASCADE;
CREATE TABLE client (id serial PRIMARY KEY, nom text NOT NULL, email text);
CREATE TABLE commande (id serial PRIMARY KEY, client_id integer NOT NULL REFERENCES client(id), total numeric);
CREATE TABLE ligne (id serial PRIMARY KEY, commande_id integer NOT NULL REFERENCES commande(id), produit text);
CREATE UNIQUE INDEX client_email_idx ON client (email);
"""


def principal():
    if not URL:
        print('MCDVIEW_TEST_DB unset: --db test skipped')
        return
    for outil in ('psql', 'pg_dump'):
        if not shutil.which(outil):
            print(f'{outil} absent: --db test skipped')
            return

    subprocess.run(['psql', URL, '-v', 'ON_ERROR_STOP=1', '-c', SCHEMA],
                   check=True, capture_output=True, text=True)

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / 'db.html'
        r = subprocess.run(
            [sys.executable, str(RACINE / 'mcdview.py'), '--db', URL, '-o', str(out)],
            capture_output=True, text=True)
        if r.returncode:
            print('ÉCHEC --db :', r.stderr.strip())
            sys.exit(1)
        html = out.read_text()

    echecs = []
    if not re.search(r'(\d+) tables', r.stdout) or '3 tables, 2 FKs' not in r.stdout:
        echecs.append(f'compte inattendu : {r.stdout.strip()!r} (attendu 3 tables, 2 FKs)')
    for nom in ('client', 'commande', 'ligne'):
        if f'"nom": "{nom}"' not in html:
            echecs.append(f'table {nom} absente de la page')
    if echecs:
        print('ÉCHECS --db :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('--db : schéma live lu via pg_dump, 3 tables / 2 FKs dans la page')


if __name__ == '__main__':
    principal()
