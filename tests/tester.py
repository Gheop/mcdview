#!/usr/bin/env python3
"""Regression and benchmark runner for mcdview.

Runs mcdview end-to-end on every model it can find:
- exemples/*.sql (committed examples) — always;
- the pgModeler sample models (when pgmodeler-cli is available);
- tests/corpus/** (local corpus, not committed — see rapatrier.sh) —
  skipped with --rapide (the pre-commit hook uses that).

For each model: generates the page in a temp dir, times it, checks the
parsed counts against pinned expectations, and looks for anomalies
(no table, tables without columns, unresolved FK targets, leftover
placeholders in the HTML). Exits non-zero on any failure.

The models are independent and most of the time goes to external converters
(pgmodeler-cli: ~0.3 s just to start, three runs for a .dbm that needs
--fix-model), so they are converted --jobs at a time, largest first so the
longest conversion starts right away; results still print in the usual order.
Per-model times are then taken under contention: use --jobs 1 for clean
per-model timings (benchmark use).
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SAMPLES = Path('/usr/share/pgmodeler')

# pinned (tables, fks) — a drift here is a parser regression (or a fix to pin)
ATTENDUS = {
    'exemples/mediatheque.sql': (12, 21),
    'exemples/pagila.sql': (16, 22),
    'exemples/northwind.sql': (14, 13),
    'exemples/chinook.sql': (11, 11),
    'exemples/boutique_v1.sql': (6, 5),   # baseline for the --diff demo
    'exemples/boutique_v2.sql': (6, 6),   # newer model in the --diff demo
    'samples/demo.dbm': (9, 8),
    # pagila.dbm content varies by pgModeler version (15/18 here, 21/40 on
    # the CI runner's build), so it stays tested but without a pinned count
    'samples/northwind.dbm': (14, 13),
    'samples/usda.dbm': (10, 11),
    'samples/cryptoconcept.dbm': (19, 19),
    'samples/3dcitydb.dbm': (60, 263),
    'conf/example.dbm': (3, 2),  # the quoted "table" is now read (was missed)
}
IGNORES = set()


def charger_mcdview():
    spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def collecter(rapide):
    modeles = [(f'exemples/{p.name}', p) for p in sorted((RACINE / 'exemples').glob('*.sql'))]
    import shutil
    if shutil.which('pgmodeler-cli') and SAMPLES.is_dir():
        for p in sorted(SAMPLES.glob('samples/*.dbm')) + [SAMPLES / 'conf/example.dbm']:
            cle = str(p.relative_to(SAMPLES))
            if cle not in IGNORES:
                modeles.append((cle, p))
    if not rapide:
        corpus = RACINE / 'tests/corpus'
        for p in sorted(corpus.rglob('*.sql')) + sorted(corpus.rglob('*.dbm')):
            modeles.append((f'corpus/{p.relative_to(corpus)}', p))
    return modeles


def anomalies_analyse(mcdview, chemin):
    """In-process parse of a .sql to spot what the counts don't show."""
    tables, fks = mcdview.analyser_sql(chemin)
    problemes = []
    sans_cols = [c for c, t in tables.items() if not t['cols']]
    if sans_cols:
        problemes.append(f'tables without columns: {sans_cols[:4]}')
    sans_cible = [f['nom'] for f in fks if not f['colcible']]
    if sans_cible:
        problemes.append(f'FKs with unresolved target column: {sans_cible[:4]}')
    return problemes


def convertir(cle, chemin, td):
    """Run the CLI on one model; returns (result, output path, elapsed ms)."""
    sortie = Path(td) / (cle.replace('/', '_') + '.html')
    cmd = [sys.executable, str(RACINE / 'mcdview.py'), str(chemin),
           '-o', str(sortie), '--lang', 'en']
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    # pgmodeler-cli occasionally fails a .dbm export transiently: one retry
    if r.returncode and chemin.suffix == '.dbm':
        r = subprocess.run(cmd, capture_output=True, text=True)
    return r, sortie, (time.perf_counter() - t0) * 1000


def principal():
    ap = argparse.ArgumentParser(description='mcdview regression/benchmark runner')
    ap.add_argument('--rapide', action='store_true',
                    help='skip tests/corpus (pre-commit mode)')
    ap.add_argument('--jobs', type=int, default=min(4, os.cpu_count() or 1),
                    help='models converted at once (default: up to 4); '
                         '1 gives clean per-model timings')
    args = ap.parse_args()

    mcdview = charger_mcdview()
    echecs, total_ms = [], 0.0
    debut = time.perf_counter()
    modeles = collecter(args.rapide)
    with tempfile.TemporaryDirectory(prefix='mcdview-tests-') as td, \
            ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        # submit the largest first (the longest conversions), print in order
        taches = {cle: pool.submit(convertir, cle, chemin, td)
                  for cle, chemin in sorted(modeles, key=lambda m: -m[1].stat().st_size)}
        for cle, chemin in modeles:
            r, sortie, ms = taches[cle].result()
            total_ms += ms
            if r.returncode:
                echecs.append(cle)
                print(f'FAIL {cle}: exit {r.returncode}: {(r.stderr or r.stdout).strip()[:200]}')
                continue
            m = re.search(r'(\d+) tables, (\d+) FKs', r.stdout)
            compte = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
            problemes = []
            attendu = ATTENDUS.get(cle)
            if attendu and compte != attendu:
                problemes.append(f'counts {compte} != pinned {attendu}')
            html = sortie.read_text() if sortie.exists() else ''
            if not html:
                problemes.append('no HTML produced')
            elif '__DONNEES__' in html or '__TITRE__' in html or '__LOGO__' in html:
                problemes.append('placeholder left in the HTML')
            if chemin.suffix == '.sql':
                problemes += anomalies_analyse(mcdview, str(chemin))
            etat = 'FAIL' if problemes else ('ok  ' if attendu else 'info')
            taille = chemin.stat().st_size
            print(f'{etat} {cle:42s} {compte[0]:4d} tables {compte[1]:4d} FKs '
                  f'{ms:7.0f} ms {taille / 1024:8.0f} KiB'
                  + ('  ' + '; '.join(problemes) if problemes else ''))
            if problemes:
                echecs.append(cle)
    print(f'\n{len(echecs)} failure(s), total {time.perf_counter() - debut:.1f} s '
          f'({total_ms / 1000:.1f} s of conversions, {max(1, args.jobs)} at a time)')
    sys.exit(1 if echecs else 0)


if __name__ == '__main__':
    principal()
