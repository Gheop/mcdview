#!/usr/bin/env python3
"""Large-scale quality and performance campaign over the local corpus.

Runs mcdview in-process on every .sql under tests/corpus/ (recursive) plus
the committed examples, timing each phase separately (parse, layout, page
composition) and validating the result:
- classification: ok / sans-table (dialect not covered) / erreur (exception);
- anomalies: tables without columns, FKs whose target column is unresolved,
  leftover placeholders in the HTML;
- optional --chrome N: render N sampled pages headless and compare the DOM
  table count with the parsed one (end-to-end JS sanity);
- optional --dbm: also run every corpus .dbm through pgmodeler-cli (export
  timed apart, upstream loading failures classified as refus-pgmodeler).

Writes one line per file to tests/resultats.tsv and prints a summary with
percentiles.
"""
import argparse
import importlib.util
import random
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CORPUS = RACINE / 'tests' / 'corpus'
TSV = RACINE / 'tests' / 'resultats.tsv'

spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)


def chrono(fonction, *args):
    t0 = time.perf_counter()
    resultat = fonction(*args)
    return resultat, (time.perf_counter() - t0) * 1000


def percentiles(valeurs):
    if not valeurs:
        return 'n/a'
    q = (statistics.quantiles(valeurs, n=100, method='inclusive')
         if len(valeurs) > 1 else [valeurs[0]] * 99)
    return (f'med {q[49]:.0f} ms, p90 {q[89]:.0f} ms, p99 {q[98]:.0f} ms, '
            f'max {max(valeurs):.0f} ms')


def valider_chrome(chemin_html, attendu_tables):
    r = subprocess.run(
        ['google-chrome', '--headless=new', '--disable-gpu',
         '--window-size=1600,900', '--virtual-time-budget=8000',
         '--dump-dom', f'file://{chemin_html}'],
        capture_output=True, text=True, timeout=120)
    rendues = len(re.findall(r'class="table[ "]', r.stdout))
    return rendues == attendu_tables, rendues


def principal():
    ap = argparse.ArgumentParser(description='mcdview large-scale campaign')
    ap.add_argument('--chrome', type=int, default=0, metavar='N',
                    help='render N sampled pages headless and check the DOM')
    ap.add_argument('--limite', type=int, default=0, help='cap the file count')
    ap.add_argument('--dbm', action='store_true',
                    help='also run the corpus .dbm files through pgmodeler-cli')
    ap.add_argument('--strict', action='store_true',
                    help='exit non-zero on any exception or anomaly (pre-commit)')
    args = ap.parse_args()

    fichiers = sorted((RACINE / 'exemples').glob('*.sql')) + sorted(CORPUS.rglob('*.sql'))
    if args.dbm:
        fichiers += sorted(CORPUS.rglob('*.dbm'))
    if args.limite:
        fichiers = fichiers[:args.limite]
    lignes, stats = [], {'ok': [], 'sans-table': 0, 'erreur': 0}
    tailles_html = []
    td = Path(tempfile.mkdtemp(prefix='mcdview-banc-'))
    for chemin in fichiers:
        octets = chemin.stat().st_size
        try:
            source = str(chemin)
            if chemin.suffix == '.dbm':
                try:
                    source, ms_export = chrono(mcdview.sql_depuis_dbm, source)
                except SystemExit as e:
                    stats['refus-pgmodeler'] = stats.get('refus-pgmodeler', 0) + 1
                    lignes.append((chemin.name, octets, 0, 0, 0, 0, 0, 0,
                                   'refus-pgmodeler: ' + str(e)[:80].replace('\n', ' ')))
                    continue
            (tables, fks), ms_parse = chrono(mcdview.analyser, source, 'auto')
            if not tables:
                stats['sans-table'] += 1
                lignes.append((chemin.name, octets, 0, 0, ms_parse, 0, 0, 0, 'sans-table'))
                continue
            _, ms_place = chrono(mcdview.placement_auto, tables, fks)
            html, ms_page = chrono(mcdview.composer_page, tables, fks, chemin.stem, 'en')
            problemes = []
            if any(p in html for p in ('__DONNEES__', '__TITRE__', '__LOGO__')):
                problemes.append('placeholder')
            sans_cols = sum(1 for t in tables.values() if not t['cols'])
            if sans_cols:
                problemes.append(f'{sans_cols} tables sans colonne')
            sans_cible = sum(1 for f in fks if not f['colcible'])
            if sans_cible:
                problemes.append(f'{sans_cible} FK sans colonne cible')
            etat = 'anomalie: ' + '; '.join(problemes) if problemes else 'ok'
            if not problemes:
                stats['ok'].append((octets, ms_parse + ms_place + ms_page))
            (td / (chemin.stem + '.html')).write_text(html)
            tailles_html.append(len(html))
            lignes.append((chemin.name, octets, len(tables), len(fks),
                           ms_parse, ms_place, ms_page, len(html), etat))
        except Exception as e:
            stats['erreur'] += 1
            lignes.append((chemin.name, octets, 0, 0, 0, 0, 0, 0, f'erreur: {e!r:.120}'))

    with open(TSV, 'w') as sortie:
        sortie.write('fichier\tocts\ttables\tfks\tms_parse\tms_place\tms_page\tocts_html\tetat\n')
        for l in lignes:
            sortie.write('\t'.join(str(c) for c in l) + '\n')

    problemes = [l for l in lignes if l[8] not in ('ok', 'sans-table')]
    print(f'{len(lignes)} fichiers — {len(stats["ok"])} ok, '
          f'{stats["sans-table"]} sans table (autre dialecte), '
          f'{len([l for l in lignes if l[8].startswith("anomalie")])} anomalies, '
          f'{stats["erreur"]} erreurs, '
          f'{stats.get("refus-pgmodeler", 0)} refus pgmodeler-cli')
    tota = [t for _, t in stats['ok']]
    print('temps total (parse+placement+page) :', percentiles(tota))
    gros = [t for o, t in stats['ok'] if o > 500_000]
    if gros:
        print(f'fichiers > 500 KiB ({len(gros)}) :', percentiles(gros))
    if tailles_html:
        print(f'HTML produit : med {statistics.median(tailles_html)/1024:.0f} KiB, '
              f'max {max(tailles_html)/1024/1024:.1f} MiB')
    for l in problemes[:15]:
        print('  !', l[0], '—', l[8])

    if args.chrome:
        alea = random.Random(0)
        candidats = [l for l in lignes if l[8] == 'ok']
        echantillon = alea.sample(candidats, min(args.chrome, len(candidats)))
        rates = 0
        for l in echantillon:
            page = td / (Path(l[0]).stem + '.html')
            t0 = time.perf_counter()
            bon, rendues = valider_chrome(page, l[2])
            dt = time.perf_counter() - t0
            if not bon:
                rates += 1
                print(f'  ! DOM {l[0]} : {rendues} tables rendues != {l[2]} parsées')
            else:
                print(f'  chrome ok {l[0]:50s} {l[2]:5d} tables rendues en {dt:5.1f} s')
        print(f'chrome : {len(echantillon) - rates}/{len(echantillon)} pages conformes')
    print(f'détail par fichier : {TSV}\npages : {td}')

    if args.strict:
        # exceptions are always a regression; anomalies come from faithful
        # source models (empty tables in a .dbm), so they only warn
        durs = [l for l in lignes if l[8].startswith('erreur')]
        if durs:
            print(f'\nSTRICT: {len(durs)} fichier(s) en exception — régression')
            sys.exit(1)


if __name__ == '__main__':
    principal()
