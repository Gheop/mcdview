#!/usr/bin/env python3
"""Content invariants over parsed models — catches silent extraction bugs.

Where grand_banc.py checks a page is produced, this checks the parsed model is
internally consistent, which surfaces mapping bugs (a lost type, a phantom PK
column, an FK pointing nowhere) that a "it renders" test never sees.

For every .sql under exemples/ and tests/corpus/ (and .dbm when pgmodeler-cli
is present), it parses via analyser(auto) and checks, per model:
  - every table has at least one column;
  - every column has a non-empty type;
  - every PK column name exists among the table's columns;
  - every FK source column exists in its table;
  - every FK target column (when set) exists in the target table.

Run `--strict` (pre-commit) to only assert the committed dialect fixtures and
examples are clean; run bare (exploration) to scan the whole local corpus and
report the worst offenders. Exits non-zero on a strict violation.
"""
import argparse
import importlib.util
import shutil
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)


def verifier(tables, fks):
    """Return a list of (kind, detail) invariant violations for one model."""
    violations = []
    for cle, t in tables.items():
        noms = {c['nom'] for c in t['cols']}
        if not t['cols']:
            violations.append(('table-sans-colonne', cle))
        for c in t['cols']:
            if not c['type']:
                violations.append(('type-vide', f'{cle}.{c["nom"]}'))
        for p in t['pk']:
            if p not in noms:
                violations.append(('pk-colonne-fantome', f'{cle}.{p}'))
    for f in fks:
        src = tables.get(f['de'])
        dst = tables.get(f['vers'])
        if src and f['col'] not in {c['nom'] for c in src['cols']}:
            violations.append(('fk-colonne-source-absente', f'{f["de"]}.{f["col"]}'))
        if dst and f['colcible'] and f['colcible'] not in {c['nom'] for c in dst['cols']}:
            violations.append(('fk-colonne-cible-absente', f'{f["vers"]}.{f["colcible"]}'))
    return violations


def collecter(strict):
    fichiers = sorted((RACINE / 'exemples').glob('*.sql'))
    fichiers += sorted((RACINE / 'tests' / 'dialectes').glob('*.sql'))
    if strict:
        return fichiers
    corpus = RACINE / 'tests' / 'corpus'
    fichiers += sorted(corpus.rglob('*.sql'))
    if shutil.which('pgmodeler-cli'):
        fichiers += sorted(corpus.rglob('*.dbm'))
        p = Path('/usr/share/pgmodeler/samples')
        if p.is_dir():
            fichiers += sorted(p.glob('*.dbm'))
    return fichiers


def principal():
    ap = argparse.ArgumentParser(description='mcdview content invariants')
    ap.add_argument('--strict', action='store_true',
                    help='only the committed examples/fixtures, and fail on any violation')
    args = ap.parse_args()

    total = Counter()
    exemples = {}   # kind -> first few offending files
    fautifs = Counter()
    scannes = 0
    for chemin in collecter(args.strict):
        try:
            tables, fks, _ = mcdview.analyser(str(chemin), 'auto')
        except SystemExit:
            continue  # a .dbm pgmodeler-cli cannot load; grand_banc covers that
        if not tables:
            continue
        scannes += 1
        vues = verifier(tables, fks)
        for kind, detail in vues:
            total[kind] += 1
            exemples.setdefault(kind, []).append(f'{chemin.name}: {detail}')
        if vues:
            fautifs[chemin.name] = len(vues)

    print(f'{scannes} modèles analysés')
    if not total:
        print('invariants : aucun problème')
        return
    for kind, n in total.most_common():
        print(f'\n{kind}: {n}')
        for ex in exemples[kind][:5]:
            print('   ', ex)

    if args.strict:
        print(f'\nSTRICT: {sum(total.values())} violation(s) dans les fixtures/exemples')
        sys.exit(1)


if __name__ == '__main__':
    principal()
