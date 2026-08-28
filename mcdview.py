#!/usr/bin/env python3
"""mcdview — interactive HTML explorer for a PostgreSQL data model.

Generates a self-contained page (no dependency) from a DDL file: overview
of tables grouped by schema, click to isolate a table with its related
tables, field detail panel (types, PK, clickable FKs, comments), search.

Usage:
    mcdview.py model.sql [-o output.html] [--titre "My project"]
                [--dbm model.dbm] [--fk-audit REGEX]

--dbm      : reuse table positions from a pgModeler model.
             Without it, mcdview computes an automatic layout.
--fk-audit : regex on FK constraint names to tag as "audit"
             (hidden by default, shown back with a checkbox).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PALETTE = ['#cdebc5', '#d6e6f5', '#a8d8b9', '#f5e3c8', '#e8d5f0',
           '#f0d0d0', '#d0e8e8', '#ede5c0', '#dcd6f7', '#f5d6a6']

# automatic-layout metrics (same orders of magnitude as the CSS rendering)
CHAR_W, ROW_H, HDR_H = 7.6, 20.5, 34
GAP_X, GAP_Y, ZONE_GAP, TARGET_H = 120, 70, 300, 2200


# keywords opening a constraint line inside a CREATE TABLE body
MOTS_CONTRAINTE = ('CONSTRAINT', 'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE',
                   'CHECK', 'EXCLUDE', 'LIKE ')


RE_COLONNE = re.compile(r'"?(\w+)"?\s+(.+)$')
RE_NOT_NULL = re.compile(r'\s*\bNOT NULL\b')
RE_DEFAUT = re.compile(r'\s*\bDEFAULT\s+(.*)$')
RE_COUPE = re.compile(r'\s+\b(?:REFERENCES|GENERATED|COLLATE|CONSTRAINT)\b')


def analyser_colonne(ligne):
    """One column line → dict, or None if it is not one."""
    cm = RE_COLONNE.match(ligne)
    if not cm:
        return None
    nom, reste = cm.groups()
    nn = bool(RE_NOT_NULL.search(reste))
    reste = RE_NOT_NULL.sub('', reste)
    defaut = ''
    dm = RE_DEFAUT.search(reste)
    if dm:
        defaut = dm.group(1).strip()
        reste = reste[:dm.start()]
    # cut what we do not represent (inline REFERENCES, GENERATED, COLLATE...)
    reste = RE_COUPE.split(reste)[0]
    return {'nom': nom, 'type': reste.strip(), 'nn': nn, 'defaut': defaut}


def analyser_sql(chemin):
    src = open(chemin).read()
    tables, fks = {}, []

    # CREATE TABLE [schema.]name ( ... ) [PARTITION BY ... / WITH ...];
    # the opening parenthesis may end the line or stand on its own
    for m in re.finditer(
            r'CREATE TABLE (?:IF NOT EXISTS )?(?:(\w+)\.)?(\w+)\s*\(\n(.*?)\n\)[^;]*;',
            src, re.S):
        sch = m.group(1) or 'public'
        nom, corps = m.group(2), m.group(3)
        cols, pk = [], []
        for ligne in corps.split('\n'):
            ligne = ligne.strip().rstrip(',')
            cm = re.match(r'(?:CONSTRAINT \w+ )?PRIMARY KEY\s*\(([^)]+)\)', ligne)
            if cm:
                pk = [c.strip() for c in cm.group(1).split(',')]
                continue
            if not ligne or ligne.startswith('--') or ligne.startswith(MOTS_CONTRAINTE):
                continue
            col = analyser_colonne(ligne)
            if col:
                cols.append(col)
        tables[f'{sch}.{nom}'] = {'schema': sch, 'nom': nom, 'cols': cols, 'pk': pk,
                                  'x': 0, 'y': 0, 'comment': '', 'colcomments': {}}

    # partitions: constraints carried by a partition are folded back into
    # the parent, and the partitions themselves do not appear in the model
    parent = {}
    for m in re.finditer(
            r'CREATE TABLE (?:(\w+)\.)?(\w+) PARTITION OF (?:(\w+)\.)?(\w+)', src):
        enfant = f"{m.group(1) or 'public'}.{m.group(2)}"
        parent[enfant] = f"{m.group(3) or 'public'}.{m.group(4)}"
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:(\w+)\.)?(\w+)\s+ATTACH PARTITION '
            r'(?:(\w+)\.)?(\w+)', src):
        enfant = f"{m.group(3) or 'public'}.{m.group(4)}"
        parent[enfant] = f"{m.group(1) or 'public'}.{m.group(2)}"
    for enfant in parent:
        tables.pop(enfant, None)

    def resoudre(cle):
        while cle in parent:
            cle = parent[cle]
        return cle

    # primary keys declared afterwards (pg_dump -s style)
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:(\w+)\.)?(\w+)\s+ADD CONSTRAINT \w+\s+'
            r'PRIMARY KEY\s*\(([^)]+)\)', src):
        cle = resoudre(f"{m.group(1) or 'public'}.{m.group(2)}")
        if cle in tables and not tables[cle]['pk']:
            tables[cle]['pk'] = [c.strip() for c in m.group(3).split(',')]

    for m in re.finditer(r"COMMENT ON TABLE (?:(\w+)\.)?(\w+) IS E?'((?:[^']|'')*)'", src):
        cle = f"{m.group(1) or 'public'}.{m.group(2)}"
        if cle in tables:
            tables[cle]['comment'] = m.group(3).replace("''", "'")
    for m in re.finditer(r"COMMENT ON COLUMN (?:(\w+)\.)?(\w+)\.(\w+) IS E?'((?:[^']|'')*)'", src):
        cle = f"{m.group(1) or 'public'}.{m.group(2)}"
        if cle in tables:
            tables[cle]['colcomments'][m.group(3)] = m.group(4).replace("''", "'")

    # FKs, including composite ones, targets without columns (= target PK)
    # and declarations carried by partitions (folded back, then deduplicated)
    vues = set()
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:(\w+)\.)?(\w+)\s+ADD CONSTRAINT (\w+)\s+'
            r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES (?:(\w+)\.)?(\w+)(?:\s*\(([^)]+)\))?',
            src):
        ssch, stab, cname, scols, dsch, dtab, dcols = m.groups()
        de = resoudre(f"{ssch or 'public'}.{stab}")
        vers = resoudre(f"{dsch or 'public'}.{dtab}")
        if de not in tables or vers not in tables:
            continue
        sources = [c.strip() for c in scols.split(',')]
        cibles = ([c.strip() for c in dcols.split(',')] if dcols
                  else tables[vers]['pk'])
        for i, scol in enumerate(sources):
            dcol = cibles[i] if i < len(cibles) else ''
            if (de, scol, vers, dcol) in vues:
                continue
            vues.add((de, scol, vers, dcol))
            fks.append({'de': de, 'col': scol, 'vers': vers,
                        'colcible': dcol, 'nom': cname, 'audit': False})
    return tables, fks


def indice_dialecte(chemin):
    """A hint appended when no table parses but another dialect shows through."""
    src = open(chemin, errors='replace').read(300000)
    if re.search(r'CREATE TABLE[^(]*`', src):
        return ' (backquoted names: this looks like MySQL DDL, mcdview reads PostgreSQL)'
    if 'AUTOINCREMENT' in src:
        return ' (AUTOINCREMENT: this looks like SQLite DDL, mcdview reads PostgreSQL)'
    return ''


def sql_depuis_dbm(chemin):
    """Export a .dbm model to SQL through pgmodeler-cli, return the SQL path.

    pgModeler resolves its <relationship> elements (which generate implicit
    columns and FKs) at export time, so delegating beats parsing the XML.
    """
    if not shutil.which('pgmodeler-cli'):
        sys.exit('reading a .dbm requires pgmodeler-cli in PATH '
                 '(or export the SQL yourself: pgmodeler-cli --export-to-file)')
    sortie = Path(tempfile.mkdtemp(prefix='mcdview-')) / 'export.sql'
    r = subprocess.run(['pgmodeler-cli', '--export-to-file', '--input', chemin,
                        '--output', str(sortie), '--silent'],
                       capture_output=True, text=True)
    if r.returncode or not sortie.exists():
        sys.exit(f'pgmodeler-cli export failed:\n{r.stdout}{r.stderr}')
    return str(sortie)


def positions_dbm(chemin, tables):
    root = ET.parse(chemin).getroot()
    couleurs = {}
    for s in root.iter('schema'):
        if s.get('fill-color'):
            couleurs[s.get('name')] = s.get('fill-color')
    for t in root.iter('table'):
        sch = t.find('schema').get('name')
        cle = f"{sch}.{t.get('name')}"
        if cle in tables:
            pos = t.find('position')
            tables[cle]['x'] = float(pos.get('x'))
            tables[cle]['y'] = float(pos.get('y'))
    return couleurs


def placement_auto(tables, fks):
    """One zone per schema, balanced columns, related tables kept close."""
    adj = defaultdict(set)
    for f in fks:
        adj[f['de']].add(f['vers'])
        adj[f['vers']].add(f['de'])

    def taille(t):
        ncols = len(t['cols'])
        long_ = max([len(t['nom']) + 4] + [len(c['nom']) + len(c['type']) + 3 for c in t['cols']] + [14])
        return max(160, long_ * CHAR_W + 30), HDR_H + ROW_H * ncols

    def ordonner(cles):
        cles = set(cles)
        degre = {c: len(adj[c] & cles) for c in cles}
        # component starts pre-sorted once: rescanning per component is O(n²)
        departs = sorted(cles, key=lambda c: (degre[c], c), reverse=True)
        resultat, vus = [], set()
        for depart in departs:
            if depart in vus:
                continue
            file_ = [depart]
            while file_:
                c = file_.pop(0)
                if c in vus:
                    continue
                vus.add(c)
                resultat.append(c)
                file_.extend(sorted((adj[c] & cles) - vus, key=lambda n: (-degre[n], n)))
        return resultat

    par_schema = defaultdict(list)
    for cle, t in tables.items():
        par_schema[t['schema']].append(cle)
    zones = sorted(par_schema, key=lambda s: -len(par_schema[s]))

    zone_x = 40.0
    for sch in zones:
        col_x, col_w, y = zone_x, 0.0, 40.0
        max_x = zone_x
        for cle in ordonner(par_schema[sch]):
            w, h = taille(tables[cle])
            if y > 40 and y + h > TARGET_H:
                col_x += col_w + GAP_X
                col_w, y = 0.0, 40.0
            tables[cle]['x'], tables[cle]['y'] = round(col_x), round(y)
            col_w = max(col_w, w)
            max_x = max(max_x, col_x + w)
            y += h + GAP_Y
        zone_x = max_x + ZONE_GAP


# UI of the generated page: the template is written in French, other
# languages are literal replacements. Each key must exist verbatim in the
# template — traduire() fails otherwise, to catch drift.
TRADUCTIONS = {
    'en': {
        '<html lang="fr">': '<html lang="en">',
        'placeholder="chercher une table…"': 'placeholder="find a table…"',
        '← vue générale (Échap)': '← overview (Esc)',
        "> FK d'audit": '> audit FKs',
        "Cliquer sur une table pour l'isoler avec ses\n"
        "tables liées et voir son détail ici.<br><br>Molette : zoom.\n"
        "Glisser : déplacer. Échap : vue générale.":
            'Click a table to isolate it with its\n'
            'related tables and see its details here.<br><br>Wheel: zoom.\n'
            'Drag: pan. Escape: overview.',
        '<div class="schema">schéma ': '<div class="schema">schema ',
        '<h4>Référencée par</h4>': '<h4>Referenced by</h4>',
        'aucune table': 'no table',
        '"cadrer ce schéma"': '"frame this schema"',
    },
}


def traduire(html, lang):
    if lang == 'fr':
        return html
    for source, cible in TRADUCTIONS[lang].items():
        if source not in html:
            sys.exit(f'cannot translate: string missing from the template: {source!r}')
        html = html.replace(source, cible)
    return html


def composer_page(tables, fks, titre, lang='fr', couleurs=None):
    """Assemble the final HTML page from parsed and positioned tables."""
    couleurs = dict(couleurs or {})
    for i, s in enumerate(sorted({t['schema'] for t in tables.values()})):
        couleurs.setdefault(s, PALETTE[i % len(PALETTE)])
    donnees = {'schemas': couleurs, 'tables': list(tables.values()), 'fks': fks}
    json_txt = json.dumps(donnees, ensure_ascii=False).replace('</', '<\\/')
    ici = Path(__file__).parent
    html = traduire((ici / 'templates' / 'explorateur.html').read_text(), lang)
    logo = (ici / 'logo.svg').read_text()
    html = html.replace('__DONNEES__', json_txt).replace('__TITRE__', titre)
    return html.replace('__LOGO__', logo.replace('width="128" height="128"',
                                                 'width="22" height="22"'))


def principal():
    ap = argparse.ArgumentParser(description="interactive HTML explorer for a PostgreSQL data model")
    ap.add_argument('sql', metavar='sql|dbm',
                    help='PostgreSQL DDL file (CREATE TABLE...) or pgModeler .dbm model')
    ap.add_argument('-o', '--sortie', help='output HTML file (default: <sql>.html)')
    ap.add_argument('--titre', default=None, help="displayed title (default: file name)")
    ap.add_argument('--dbm', help='pgModeler model to reuse table positions from')
    ap.add_argument('--fk-audit', default=None, metavar='REGEX',
                    help="regex of FK constraint names to tag as audit (hidden by default)")
    ap.add_argument('--lang', default='fr', choices=['fr'] + sorted(TRADUCTIONS),
                    help="language of the page UI (default: fr)")
    args = ap.parse_args()

    source = args.sql
    if source.endswith('.dbm'):
        if not args.dbm:
            args.dbm = source  # the model provides its own positions
        source = sql_depuis_dbm(source)
    tables, fks = analyser_sql(source)
    if not tables:
        sys.exit('no table found: the DDL must contain CREATE TABLE statements'
                 + indice_dialecte(source))

    couleurs = {}
    if args.dbm:
        couleurs = positions_dbm(args.dbm, tables)
    if not args.dbm or all(t['x'] == 0 and t['y'] == 0 for t in tables.values()):
        placement_auto(tables, fks)

    if args.fk_audit:
        motif = re.compile(args.fk_audit)
        for f in fks:
            f['audit'] = bool(motif.search(f['nom']))

    titre = args.titre or Path(args.sql).stem
    sortie = args.sortie or str(Path(args.sql).with_suffix('.html'))
    Path(sortie).write_text(composer_page(tables, fks, titre, args.lang, couleurs))
    naudit = sum(1 for f in fks if f['audit'])
    print(f'{len(tables)} tables, {len(fks)} FKs'
          + (f' (including {naudit} audit FKs)' if naudit else '') + f' → {sortie}')


if __name__ == '__main__':
    principal()
