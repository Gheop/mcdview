#!/usr/bin/env python3
"""PostgreSQL-parser edge cases that regressed or are easy to break: inline
column primary keys, and the phantom-PK traps a naive `PRIMARY KEY in line`
check falls into (a DEFAULT/CHECK/comment mentioning the words)."""
import importlib.util
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)


def tables_de(sql):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'x.sql'
        p.write_text(sql)
        return dict(mcdview.analyser_sql(str(p))[0])


def principal():
    echecs = []

    # inline column PRIMARY KEY is detected and kept out of the type
    t = tables_de('CREATE TABLE public.a (\n id serial PRIMARY KEY,\n nom text\n);')
    a = t['public.a']
    if a['pk'] != ['id']:
        echecs.append(f'inline PK: pk={a["pk"]} != [id]')
    if next(c['type'] for c in a['cols'] if c['nom'] == 'id') != 'serial':
        echecs.append('inline PK: "PRIMARY KEY" a fui dans le type de id')

    # a DEFAULT / CHECK / comment mentioning "PRIMARY KEY" must NOT create a PK
    t = tables_de(
        "CREATE TABLE public.b (\n"
        "  id integer NOT NULL PRIMARY KEY,\n"
        "  status text DEFAULT 'PRIMARY KEY',\n"
        "  label text CHECK (label <> 'PRIMARY KEY'),\n"
        "  qty integer, -- was PRIMARY KEY once\n"
        "  note text\n);")
    if t['public.b']['pk'] != ['id']:
        echecs.append(f'phantom PK: pk={t["public.b"]["pk"]} != [id]')
    qty = next(c for c in t['public.b']['cols'] if c['nom'] == 'qty')
    if qty['type'] != 'integer':
        echecs.append(f'inline comment a fui dans le type: {qty["type"]!r}')

    # an ALTER-declared PK must win when a literal earlier said "PRIMARY KEY"
    t = tables_de(
        "CREATE TABLE public.c (\n  real_id integer NOT NULL,\n"
        "  code text DEFAULT 'PRIMARY KEY'\n);\n"
        "ALTER TABLE ONLY public.c ADD CONSTRAINT c_pk PRIMARY KEY (real_id);")
    if t['public.c']['pk'] != ['real_id']:
        echecs.append(f'ALTER PK écrasée par un faux inline: {t["public.c"]["pk"]}')

    # table-level PRIMARY KEY (col list) still works
    t = tables_de('CREATE TABLE public.d (\n a integer,\n b integer,\n'
                  ' PRIMARY KEY (a, b)\n);')
    if t['public.d']['pk'] != ['a', 'b']:
        echecs.append(f'PK composite table-level: {t["public.d"]["pk"]}')

    # a FK constraint wrapped across lines (pg_dump style) must not create a
    # phantom column named REFERENCES
    t = tables_de(
        'CREATE TABLE public.a (\n'
        '  id integer PRIMARY KEY,\n'
        '  b_id integer,\n'
        '  CONSTRAINT a_b_fkey FOREIGN KEY (b_id)\n'
        '      REFERENCES public.b (id)\n'
        ');')
    noms = [c['nom'] for c in t['public.a']['cols']]
    if 'REFERENCES' in noms or noms != ['id', 'b_id']:
        echecs.append(f'FK multi-ligne: colonnes={noms} (REFERENCES fantôme ?)')

    # single-line / compact CREATE TABLE (no newline after the open paren) is
    # parsed by the built-in parser, not only via sqlglot
    t = tables_de("CREATE TABLE t (a integer PRIMARY KEY, b numeric(10,2), c text);")
    tt = t.get('public.t', {})
    noms = [c['nom'] for c in tt.get('cols', [])]
    if noms != ['a', 'b', 'c'] or tt.get('pk') != ['a']:
        echecs.append(f'single-line: cols={noms} pk={tt.get("pk")}')
    typ_b = next((c['type'] for c in tt.get('cols', []) if c['nom'] == 'b'), None)
    if typ_b != 'numeric(10,2)':  # comma inside the type must not split
        echecs.append(f'single-line: type de b = {typ_b!r} (numeric(10,2) attendu)')
    # a comma/paren inside a string literal must not split the body
    t = tables_de("CREATE TABLE u (a text DEFAULT 'x,(y)', b integer);")
    if [c['nom'] for c in t.get('public.u', {}).get('cols', [])] != ['a', 'b']:
        echecs.append('single-line: littéral avec ,/() a cassé le découpage')

    # indexes and unique constraints are extracted
    t = tables_de(
        'CREATE TABLE public.e (\n id serial PRIMARY KEY,\n email text\n);\n'
        'CREATE UNIQUE INDEX e_email ON public.e (email);\n'
        'CREATE INDEX e_id ON public.e (id);')
    idx = {i['nom']: i for i in t['public.e']['index']}
    if idx.get('e_email', {}).get('unique') is not True or idx.get('e_id', {}).get('unique') is not False:
        echecs.append(f'index: extraction inattendue ({list(idx)})')

    # several input files are merged into one model, cross-file FKs resolved
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        Path(td, 'a.sql').write_text('CREATE TABLE client (\n id serial PRIMARY KEY\n);')
        Path(td, 'b.sql').write_text(
            'CREATE TABLE commande (\n id serial PRIMARY KEY,\n client_id integer\n);\n'
            'ALTER TABLE ONLY commande ADD CONSTRAINT fk '
            'FOREIGN KEY (client_id) REFERENCES client(id);')
        out = Path(td, 'm.html')
        r = subprocess.run(
            [sys.executable, str(RACINE / 'mcdview.py'),
             str(Path(td, 'a.sql')), str(Path(td, 'b.sql')), '-o', str(out)],
            capture_output=True, text=True)
        if '2 tables, 1 FKs' not in r.stdout:
            echecs.append(f'merge multi-fichiers: {r.stdout.strip()!r} (attendu 2 tables, 1 FK)')

    # --diagnose emits JSON and never fails (exit 0), whatever the input
    import json as _json
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        bon = Path(td) / 'a.sql'
        bon.write_text('CREATE TABLE t (\n a integer PRIMARY KEY,\n b text\n);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'),
                            str(bon), '--diagnose'], capture_output=True, text=True)
        d = _json.loads(r.stdout)
        if r.returncode != 0 or d['status'] != 'ok' or d['tables'] != 1:
            echecs.append(f'--diagnose ok: {r.returncode} {d.get("status")}')
        mauvais = Path(td) / 'b.mwb'
        mauvais.write_text('not a zip')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'),
                            str(mauvais), '--diagnose'], capture_output=True, text=True)
        d = _json.loads(r.stdout)
        if r.returncode != 0 or d['status'] != 'error':
            echecs.append(f'--diagnose error: exit={r.returncode} status={d.get("status")}')

    if echecs:
        print('ÉCHECS parser :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('parser : PK inline, pas de PK fantôme, merge multi-fichiers OK')


if __name__ == '__main__':
    principal()
