#!/usr/bin/env python3
"""Security checks: XSS escaping and denial-of-service resistance.

- Committed hostile inputs (tests/malveillant/*.sql) plus generated ReDoS
  bombs must never produce executable markup and must finish well under a
  time budget. Exits non-zero on any failure. Fast (no browser, no network),
  so it runs in the pre-commit hook.
"""
import importlib.util
import re
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)

# the payloads carried by tests/malveillant/xss.sql, in raw injectable form
MARQUEURS = ['alert(1)', 'alert(2)', 'alert(3)', 'alert(4)', 'alert(5)']

BUDGET_MS = 2000  # a single file must parse+build in under 2 s


def page_de(chemin):
    tables, fks = mcdview.analyser_sql(str(chemin))
    mcdview.placement_auto(tables, fks)
    return mcdview.composer_page(tables, fks, chemin.stem, 'en')


def ilot_json(html):
    """The `const D = {...};` data island — the only place model data lands."""
    m = re.search(r'const D = (.*?);\nconst plan', html, re.S)
    return m.group(1) if m else ''


def verifier_xss(echecs):
    chemin = RACINE / 'tests' / 'malveillant' / 'xss.sql'
    html = page_de(chemin)
    ilot = ilot_json(html)
    if not ilot:
        echecs.append('xss.sql: îlot JSON introuvable dans la page')
        return
    # core invariant: every '<' in the injected data is escaped to <, so
    # nothing in the data can open a tag or close the surrounding <script>.
    if '<' in ilot:
        contexte = ilot[max(0, ilot.index('<') - 30):ilot.index('<') + 10]
        echecs.append(f'xss.sql: "<" brut dans le JSON injecté : ...{contexte}...')
    if '</script' in ilot.lower():
        echecs.append('xss.sql: "</script" brut dans le JSON injecté (évasion possible)')
    # the payloads must survive as inert escaped text (parsing not broken)
    for marqueur in MARQUEURS:
        if marqueur not in html:
            echecs.append(f'xss.sql: charge {marqueur} disparue (parsing cassé ?)')
    # the page title path is escaped too
    tables, fks = mcdview.analyser_sql(str(chemin))
    if '<script>alert(0)' in mcdview.composer_page(
            tables, fks, '<script>alert(0)</script>', 'en'):
        echecs.append('titre: balise <script> non échappée dans le titre')


def verifier_dos(echecs):
    bombes = {
        'ouvertures orphelines': 'CREATE TABLE a (\n' * 3000 + 'x' * 800000,
        'alter sans fin': 'ALTER TABLE ONLY a.b\n    ADD CONSTRAINT c FOREIGN KEY (x)\n' * 40000,
        'quotes sans fin': "COMMENT ON TABLE a.b IS '" + "x''" * 300000,
        'points-virgules': ');\n' * 500000,
        'colonnes sans fin': 'CREATE TABLE t (\n' + 'a integer,\n' * 20000,
    }
    with tempfile.TemporaryDirectory() as td:
        cibles = [(f.name, f) for f in (RACINE / 'tests' / 'malveillant').glob('*.sql')]
        for nom, contenu in bombes.items():
            p = Path(td) / re.sub(r'\W', '_', nom)
            p.write_text(contenu)
            cibles.append((nom, p))
        for nom, chemin in cibles:
            t0 = time.perf_counter()
            try:
                mcdview.analyser_sql(str(chemin))
            except Exception as e:
                echecs.append(f'{nom}: exception {e!r}')
                continue
            ms = (time.perf_counter() - t0) * 1000
            etat = 'OK ' if ms < BUDGET_MS else 'LENT'
            print(f'  {etat} {nom:24s} {chemin.stat().st_size // 1024:5d} KiB {ms:7.0f} ms')
            if ms >= BUDGET_MS:
                echecs.append(f'{nom}: {ms:.0f} ms > budget {BUDGET_MS} ms (DoS)')


def principal():
    echecs = []
    verifier_xss(echecs)
    verifier_dos(echecs)
    if echecs:
        print('\nÉCHECS sécurité :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('\nsécurité : XSS échappé, aucune bombe au-dessus du budget')


if __name__ == '__main__':
    principal()
