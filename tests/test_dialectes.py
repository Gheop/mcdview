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

# fichier : (dialecte, tables, fks, {table: pk}, {fk cols → nom attendu})
CAS = {
    'dialectes/boutique.mysql.sql': ('auto', 3, 2, {
        'public.client': ['id'], 'public.commande': ['id'], 'public.ligne': ['id']}, {}),
    # real `mysqldump --no-data` output: backtick quoting, named inline
    # CONSTRAINT FKs, composite PK. Locks the FK-name recovery on the sqlglot
    # path (the exact SQL a `--db mysql://…` dump feeds the parser).
    'dialectes/boutique.mariadb.sql': ('auto', 3, 2, {
        'public.client': ['id'], 'public.commande': ['id'],
        'public.ligne': ['commande_id', 'produit']},
        {'client_id': 'fk_cmd_client', 'commande_id': 'fk_ligne_cmd'}),
    'dialectes/notes.sqlite.sql': ('auto', 4, 3, {
        'public.note_etiquette': ['note_id', 'etiquette_id']}, {}),
    'dialectes/ventes.tsql.sql': ('auto', 2, 1, {
        'dbo.Customer': ['CustomerID'], 'dbo.Order': ['OrderID']}, {}),
}


def principal():
    try:
        import sqlglot  # noqa: F401
    except ImportError:
        print('sqlglot absent: dialects test skipped (optional dependency)')
        return
    echecs = []
    for rel, (dialecte, nt, nf, pks, noms_fk) in CAS.items():
        chemin = RACINE / 'tests' / rel
        tables, fks, _ = mcdview.analyser(str(chemin), dialecte)
        if len(tables) != nt:
            echecs.append(f'{rel}: {len(tables)} tables != {nt}')
        if len(fks) != nf:
            echecs.append(f'{rel}: {len(fks)} FKs != {nf}')
        for col, nom in noms_fk.items():
            trouve = next((f['nom'] for f in fks if f['col'] == col), None)
            if trouve != nom:
                echecs.append(f'{rel}: FK {col} nom = {trouve!r} != {nom!r}')
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
    # indexes on the sqlglot path (single-line DDL falls here too): CREATE
    # [UNIQUE] INDEX, ALTER ADD CONSTRAINT UNIQUE, inline UNIQUE
    import tempfile
    from pathlib import Path
    ddl = ("CREATE TABLE client (id serial PRIMARY KEY, email text, ville text);\n"
           "CREATE UNIQUE INDEX client_email_idx ON client (email);\n"
           "CREATE INDEX client_ville_idx ON client (ville);\n")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'x.sql'
        p.write_text(ddl)
        tables, _, _ = mcdview.analyser(str(p), 'auto')
    idx = {i['nom']: i for i in tables['public.client']['index']}
    if idx.get('client_email_idx', {}).get('unique') is not True:
        echecs.append(f'sqlglot index: UNIQUE non capté ({list(idx)})')
    if idx.get('client_ville_idx', {}).get('unique') is not False:
        echecs.append(f'sqlglot index: index non-unique non capté ({list(idx)})')

    if echecs:
        print('\nÉCHECS dialectes :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('\ndialectes : MySQL/SQLite + index (chemin sqlglot) OK')


if __name__ == '__main__':
    principal()
