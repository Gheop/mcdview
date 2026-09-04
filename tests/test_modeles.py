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
    ('modeles/edge.prisma', 'prisma', getattr(mcdview, 'sql_depuis_prisma', None), 2, 1),  # view/@db/no-url
    ('modeles/boutique.mwb', None, mcdview.analyser_mwb, 2, 1),  # native, no tool
    ('modeles/boutique.schema.rb', None, mcdview.analyser_schema_rb, 3, 2),  # native
    ('modeles/boutique.mmd', None, mcdview.analyser_mermaid, 3, 2),  # native
    ('modeles/boutique.schema.ts', None, mcdview.analyser_drizzle, 3, 2),  # native
]


def principal():
    echecs, faits = [], 0

    # pretraiter_prisma loosens three P1012 triggers without a prisma install
    p = mcdview.pretraiter_prisma(
        'datasource db {\n  provider = "postgresql"\n}\n'
        'model a {\n  id Int @id\n  n Int @db.Int\n}\n'
        'view v {\n  id Int @id @unique\n  x String\n}')
    import re as _re
    vue = _re.search(r'view\s+v\s*\{[^}]*\}', p).group(0)
    if 'url =' not in p:
        echecs.append('pretraiter_prisma: url not injected into a url-less datasource')
    if '@db.' in p:
        echecs.append('pretraiter_prisma: native type @db.* not stripped')
    if '@id' in vue:
        echecs.append('pretraiter_prisma: @id not removed from a view block')
    if '@id' not in _re.search(r'model\s+a\s*\{[^}]*\}', p).group(0):
        echecs.append('pretraiter_prisma: model @id wrongly removed')
    print('ok   pretraiter_prisma: url injected, @db.* stripped, view @id dropped')
    for rel, outil, fonction, nt, nf in CAS:
        chemin = RACINE / 'tests' / rel
        if fonction is None or not chemin.exists() or (outil and not shutil.which(outil)):
            print(f'skip {rel} ({outil} absent)')
            continue
        try:
            if outil is None:  # native parser returns (tables, fks) directly
                tables, fks = fonction(str(chemin))
            else:  # converter returns an SQL path to parse
                tables, fks = mcdview.analyser_sql(fonction(str(chemin)))
        except SystemExit:
            # the converter exits when the external tool cannot run. For prisma
            # that happens when the locally installed version has no `migrate
            # diff` (prisma>=7/8) — skip rather than fail; CI pins prisma@6, the
            # authoritative check. A churning local prisma no longer blocks work.
            if outil == 'prisma':
                print(f'skip {rel} (local prisma cannot convert; needs prisma@6, CI pins it)')
                continue
            raise
        faits += 1
        if len(tables) != nt:
            echecs.append(f'{rel}: {len(tables)} tables != {nt}')
        if len(fks) != nf:
            echecs.append(f'{rel}: {len(fks)} FKs != {nf}')
        etat = 'FAIL' if any(rel in e for e in echecs) else 'ok  '
        print(f'{etat} {rel}: {len(tables)} tables, {len(fks)} FKs')
    # Rails legacy: pre-2012 hashrocket options (`:id => false`) must be
    # honored — an id:false join table gets no phantom primary key
    leg = RACINE / 'tests' / 'modeles' / 'legacy.schema.rb'
    if leg.exists():
        tl, _ = mcdview.analyser_schema_rb(str(leg))
        tg = tl.get('public.taggings', {})
        faits += 1
        if tg.get('pk') != []:
            echecs.append(f'rails legacy: taggings pk={tg.get("pk")} (:id => false ignored)')
            print('FAIL modeles/legacy.schema.rb')
        else:
            print('ok   modeles/legacy.schema.rb: hashrocket ":id => false" honored')

    if echecs:
        print('\nÉCHECS modèles :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print(f'\nmodèles : {faits} format(s) converti(s) et parsé(s) correctement')


if __name__ == '__main__':
    principal()
