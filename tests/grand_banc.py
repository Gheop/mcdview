#!/usr/bin/env python3
"""Large-scale quality and performance campaign over the whole local corpus.

Runs mcdview in-process on every model file under tests/corpus/ (recursive),
ALL formats — .sql plus the native/converter parsers — timing each phase
(parse, layout, page) and validating the result:
- classification: ok / sans-table (dialect not covered) / erreur (exception);
- anomalies: tables without columns, FKs whose target column is unresolved,
  phantom PK columns, leftover placeholders in the HTML;
- a per-format benchmark breakdown (count + timing percentiles), so a slow
  parser stands out;
- optional --chrome N: render N sampled pages headless and compare the DOM
  table count with the parsed one (end-to-end JS sanity).

External-tool formats are gated: .dbm needs --dbm (pgmodeler-cli), .dbml/.prisma
need --converters (dbml2sql / prisma). Native formats always run. Writes one
line per file to tests/resultats.tsv and prints a summary with percentiles.
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

# extension -> format label. Native formats need no external tool.
NATIFS = {'.mwb': 'mwb', '.rb': 'rails', '.mmd': 'mermaid', '.mermaid': 'mermaid',
          '.md': 'mermaid', '.ts': 'drizzle'}
CONVERTISSEURS = {'.dbml': 'dbml', '.prisma': 'prisma'}


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


def charger_fichier(chemin, fmt):
    """Return (tables, fks) for one file, dispatched by format."""
    s = str(chemin)
    if fmt == 'sql':
        return mcdview.analyser(s, 'auto')[:2]
    if fmt == 'dbm':
        return mcdview.analyser(mcdview.sql_depuis_dbm(s), 'postgres')[:2]
    if fmt == 'dbml':
        return mcdview.analyser(mcdview.sql_depuis_dbml(s), 'postgres')[:2]
    if fmt == 'prisma':
        return mcdview.analyser(mcdview.sql_depuis_prisma(s), 'auto')[:2]
    if fmt == 'mwb':
        return mcdview.normaliser_casse(*mcdview.analyser_mwb(s))
    if fmt == 'rails':
        return mcdview.normaliser_casse(*mcdview.analyser_schema_rb(s))
    if fmt == 'mermaid':
        return mcdview.normaliser_casse(*mcdview.analyser_mermaid(s))
    if fmt == 'drizzle':
        return mcdview.normaliser_casse(*mcdview.analyser_drizzle(s))
    raise ValueError(fmt)


def anomalies_de(tables, fks, html):
    problemes = []
    if any(p in html for p in ('__DONNEES__', '__TITRE__', '__LOGO__')):
        problemes.append('placeholder')
    sans_cols = sum(1 for t in tables.values() if not t['cols'])
    if sans_cols:
        problemes.append(f'{sans_cols} tables sans colonne')
    sans_cible = sum(1 for f in fks if not f['colcible'])
    if sans_cible:
        problemes.append(f'{sans_cible} FK sans colonne cible')
    # a PK/FK naming a column the table does not have (phantom)
    fantomes = 0
    for t in tables.values():
        noms = {c['nom'] for c in t['cols']}
        fantomes += sum(1 for p in t['pk'] if p not in noms)
    for f in fks:
        src = tables.get(f['de'])
        if src and f['col'] and f['col'] not in {c['nom'] for c in src['cols']}:
            fantomes += 1
    if fantomes:
        problemes.append(f'{fantomes} colonnes PK/FK fantômes')
    return problemes


def principal():
    ap = argparse.ArgumentParser(description='mcdview large-scale campaign (all formats)')
    ap.add_argument('--chrome', type=int, default=0, metavar='N',
                    help='render N sampled pages headless and check the DOM')
    ap.add_argument('--limite', type=int, default=0, help='cap the file count')
    ap.add_argument('--dbm', action='store_true',
                    help='also run the corpus .dbm files (pgmodeler-cli)')
    ap.add_argument('--converters', action='store_true',
                    help='also run .dbml/.prisma (dbml2sql / prisma)')
    ap.add_argument('--budget', type=float, default=2000, metavar='MS',
                    help='per-file time budget in ms; exceeding it is an anomaly')
    ap.add_argument('--strict', action='store_true',
                    help='exit non-zero on any exception (pre-commit)')
    args = ap.parse_args()

    # build the (path, format) work list
    travaux = [(p, 'sql') for p in sorted((RACINE / 'exemples').glob('*.sql'))]
    travaux += [(p, 'sql') for p in sorted(CORPUS.rglob('*.sql'))]
    for ext, fmt in NATIFS.items():
        travaux += [(p, fmt) for p in sorted(CORPUS.rglob('*' + ext))]
    if args.dbm:
        travaux += [(p, 'dbm') for p in sorted(CORPUS.rglob('*.dbm'))]
    if args.converters:
        for ext, fmt in CONVERTISSEURS.items():
            travaux += [(p, fmt) for p in sorted(CORPUS.rglob('*' + ext))]
    if args.limite:
        travaux = travaux[:args.limite]

    lignes = []
    stats = {'ok': [], 'sans-table': 0, 'erreur': 0}
    par_format = {}          # fmt -> {'n','ok','sans','err','anom','temps':[]}
    tailles_html = []
    td = Path(tempfile.mkdtemp(prefix='mcdview-banc-'))
    for chemin, fmt in travaux:
        pf = par_format.setdefault(fmt, {'n': 0, 'ok': 0, 'sans': 0, 'err': 0,
                                         'anom': 0, 'temps': []})
        pf['n'] += 1
        octets = chemin.stat().st_size
        try:
            # external-tool formats (dbm/dbml/prisma) sys.exit when the upstream
            # tool rejects a file — that is a conversion refusal, not a crash
            if fmt in ('dbm', 'dbml', 'prisma'):
                try:
                    (tables, fks), ms_parse = chrono(charger_fichier, chemin, fmt)
                except SystemExit as e:
                    stats['conv-échec'] = stats.get('conv-échec', 0) + 1
                    pf['sans'] += 1
                    lignes.append((chemin.name, fmt, octets, 0, 0, 0, 0, 0, 0,
                                   'conv-échec: ' + str(e)[:80].replace('\n', ' ')))
                    continue
            else:
                (tables, fks), ms_parse = chrono(charger_fichier, chemin, fmt)
            if not tables:
                stats['sans-table'] += 1
                pf['sans'] += 1
                lignes.append((chemin.name, fmt, octets, 0, 0, ms_parse, 0, 0, 0, 'sans-table'))
                continue
            _, ms_place = chrono(mcdview.placement_auto, tables, fks)
            html, ms_page = chrono(mcdview.composer_page, tables, fks, chemin.stem, 'en')
            total_ms = ms_parse + ms_place + ms_page
            problemes = anomalies_de(tables, fks, html)
            if total_ms > args.budget:
                problemes.append(f'{total_ms:.0f} ms > budget {args.budget:.0f} ms')
            etat = 'anomalie: ' + '; '.join(problemes) if problemes else 'ok'
            if not problemes:
                stats['ok'].append((octets, total_ms))
                pf['ok'] += 1
                pf['temps'].append(total_ms)
            else:
                pf['anom'] += 1
            # only keep the pages on disk when --chrome will re-open them;
            # otherwise writing ~13k pages per run just fills the temp dir
            if args.chrome:
                (td / (chemin.stem + '.html')).write_text(html)
            tailles_html.append(len(html))
            lignes.append((chemin.name, fmt, octets, len(tables), len(fks),
                           ms_parse, ms_place, ms_page, len(html), etat))
        except Exception as e:
            stats['erreur'] += 1
            pf['err'] += 1
            lignes.append((chemin.name, fmt, octets, 0, 0, 0, 0, 0, 0, f'erreur: {e!r:.160}'))

    with open(TSV, 'w') as sortie:
        sortie.write('fichier\tformat\tocts\ttables\tfks\tms_parse\tms_place\tms_page\tocts_html\tetat\n')
        for ligne in lignes:
            sortie.write('\t'.join(str(c) for c in ligne) + '\n')

    benins = ('ok', 'sans-table')
    problemes = [ligne for ligne in lignes
                 if ligne[9] not in benins and not ligne[9].startswith('conv-échec')]
    anomalies = [ligne for ligne in lignes if ligne[9].startswith('anomalie')]
    conv = stats.get('conv-échec', 0) + stats.get('refus-pgmodeler', 0)
    print(f'{len(lignes)} fichiers — {len(stats["ok"])} ok, '
          f'{stats["sans-table"]} sans table (autre dialecte), '
          f'{len(anomalies)} anomalies, {stats["erreur"]} erreurs, '
          f'{conv} conversions refusées (tool amont)')
    print('temps total (parse+placement+page) :', percentiles([t for _, t in stats['ok']]))
    gros = [t for o, t in stats['ok'] if o > 500_000]
    if gros:
        print(f'fichiers > 500 KiB ({len(gros)}) :', percentiles(gros))
    if tailles_html:
        print(f'HTML produit : med {statistics.median(tailles_html)/1024:.0f} KiB, '
              f'max {max(tailles_html)/1024/1024:.1f} MiB')
    print('\npar format :')
    print(f'  {"format":9s} {"n":>6s} {"ok":>6s} {"sans":>5s} {"anom":>5s} {"err":>4s}   timing')
    for fmt in sorted(par_format):
        p = par_format[fmt]
        print(f'  {fmt:9s} {p["n"]:6d} {p["ok"]:6d} {p["sans"]:5d} {p["anom"]:5d} '
              f'{p["err"]:4d}   {percentiles(p["temps"])}')
    for ligne in problemes[:25]:
        print('  !', ligne[0], f'[{ligne[1]}]', '—', ligne[9])

    if args.chrome:
        alea = random.Random(0)
        candidats = [ligne for ligne in lignes if ligne[9] == 'ok']
        echantillon = alea.sample(candidats, min(args.chrome, len(candidats)))
        rates = 0
        for ligne in echantillon:
            page = td / (Path(ligne[0]).stem + '.html')
            bon, rendues = valider_chrome(page, ligne[3])
            if not bon:
                rates += 1
                print(f'  ! DOM {ligne[0]} : {rendues} tables rendues != {ligne[3]} parsées')
        print(f'chrome : {len(echantillon) - rates}/{len(echantillon)} pages conformes')
    print(f'détail par fichier : {TSV}')
    if args.chrome:
        print(f'pages : {td}')
    else:
        import shutil
        shutil.rmtree(td, ignore_errors=True)  # nothing kept: don't leave it behind

    if args.strict:
        durs = [ligne for ligne in lignes if ligne[9].startswith('erreur')]
        if durs:
            print(f'\nSTRICT: {len(durs)} fichier(s) en exception — régression')
            sys.exit(1)


if __name__ == '__main__':
    principal()
