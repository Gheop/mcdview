#!/usr/bin/env python3
"""Non-PostgreSQL dialects through the optional sqlglot backend.

Checks that committed MySQL and SQLite fixtures parse to the expected tables,
FKs and primary keys, and that a page is produced. Skips (exit 0) when sqlglot
is not installed, since it is an optional dependency; CI installs it.
"""
import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)

# fichier : (dialecte, tables, fks, {table: pk})
CAS = {
    'dialectes/boutique.mysql.sql': ('auto', 3, 2, {
        'public.client': ['id'], 'public.commande': ['id'], 'public.ligne': ['id']}),
    'dialectes/notes.sqlite.sql': ('auto', 4, 3, {
        'public.note_etiquette': ['note_id', 'etiquette_id']}),
}


def principal():
    try:
        import sqlglot  # noqa: F401
    except ImportError:
        print('sqlglot absent: dialects test skipped (optional dependency)')
        return
    echecs = []
    for rel, (dialecte, nt, nf, pks) in CAS.items():
        chemin = RACINE / 'tests' / rel
        tables, fks = mcdview.analyser(str(chemin), dialecte)
        if len(tables) != nt:
            echecs.append(f'{rel}: {len(tables)} tables != {nt}')
        if len(fks) != nf:
            echecs.append(f'{rel}: {len(fks)} FKs != {nf}')
        for cle, pk in pks.items():
            if cle not in tables:
                echecs.append(f'{rel}: table {cle} absente')
            elif tables[cle]['pk'] != pk:
                echecs.append(f'{rel}: PK {cle} = {tables[cle]["pk"]} != {pk}')
        if tables:
            mcdview.placement_auto(tables, fks)
            html = mcdview.composer_page(tables, fks, 'x', 'en')
            if '__DONNEES__' in html:
                echecs.append(f'{rel}: page non produite')
        print(f'{"FAIL" if any(rel in e for e in echecs) else "ok  "} {rel}: '
              f'{len(tables)} tables, {len(fks)} FKs')
    if echecs:
        print('\nÉCHECS dialectes :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('\ndialectes : MySQL et SQLite parsés correctement')


if __name__ == '__main__':
    principal()
