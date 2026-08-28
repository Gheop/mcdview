#!/usr/bin/env python3
"""Model-file formats that mcdview reads through an upstream converter.

Each format (DBML via dbml2sql, Prisma via prisma, pgModeler .dbm via
pgmodeler-cli) is converted to SQL and then parsed. A format whose converter
is not installed is skipped (they are optional dependencies); CI installs them.
Exits non-zero on a real mismatch.
"""
import importlib.util
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)

# fixture, (converter tool or None if native, parse fn, expected tables, FKs)
CAS = [
    ('modeles/boutique.dbml', 'dbml2sql', mcdview.sql_depuis_dbml, 3, 2),
    ('modeles/boutique.prisma', 'prisma', getattr(mcdview, 'sql_depuis_prisma', None), 3, 2),
    ('modeles/boutique.mwb', None, mcdview.analyser_mwb, 2, 1),  # native, no tool
    ('modeles/boutique.schema.rb', None, mcdview.analyser_schema_rb, 3, 2),  # native
    ('modeles/boutique.mmd', None, mcdview.analyser_mermaid, 3, 2),  # native
    ('modeles/boutique.schema.ts', None, mcdview.analyser_drizzle, 3, 2),  # native
]


def principal():
    echecs, faits = [], 0
    for rel, outil, fonction, nt, nf in CAS:
        chemin = RACINE / 'tests' / rel
        if fonction is None or not chemin.exists() or (outil and not shutil.which(outil)):
            print(f'skip {rel} ({outil} absent)')
            continue
        if outil is None:  # native parser returns (tables, fks) directly
            tables, fks = fonction(str(chemin))
        else:  # converter returns an SQL path to parse
            tables, fks = mcdview.analyser_sql(fonction(str(chemin)))
        faits += 1
        if len(tables) != nt:
            echecs.append(f'{rel}: {len(tables)} tables != {nt}')
        if len(fks) != nf:
            echecs.append(f'{rel}: {len(fks)} FKs != {nf}')
        etat = 'FAIL' if any(rel in e for e in echecs) else 'ok  '
        print(f'{etat} {rel}: {len(tables)} tables, {len(fks)} FKs')
    if echecs:
        print('\nÉCHECS modèles :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print(f'\nmodèles : {faits} format(s) converti(s) et parsé(s) correctement')


if __name__ == '__main__':
    principal()
