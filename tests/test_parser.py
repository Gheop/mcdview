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

    if echecs:
        print('ÉCHECS parser :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('parser : PK inline OK, aucun PK fantôme (DEFAULT/CHECK/commentaire)')


if __name__ == '__main__':
    principal()
