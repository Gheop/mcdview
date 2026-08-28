#!/usr/bin/env python3
"""mcdview — explorateur HTML interactif d'un modèle de données PostgreSQL.

Génère une page autonome (aucune dépendance) depuis un fichier DDL : vue
d'ensemble des tables par schéma, clic pour isoler une table avec ses tables
liées, panneau de détail des champs (types, PK, FK cliquables, commentaires),
recherche.

Usage :
    mcdview.py modele.sql [-o sortie.html] [--titre "Mon projet"]
                [--dbm modele.dbm] [--fk-audit REGEX]

--dbm      : reprend les positions des tables d'un modèle pgModeler.
             Sans lui, mcdview calcule un placement automatique.
--fk-audit : regex sur le nom des contraintes FK à classer « audit »
             (masquées par défaut, réaffichables d'une case à cocher).
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

PALETTE = ['#cdebc5', '#d6e6f5', '#a8d8b9', '#f5e3c8', '#e8d5f0',
           '#f0d0d0', '#d0e8e8', '#ede5c0', '#dcd6f7', '#f5d6a6']

# métriques du placement automatique (mêmes ordres de grandeur que le rendu CSS)
CHAR_W, ROW_H, HDR_H = 7.6, 20.5, 34
GAP_X, GAP_Y, ZONE_GAP, TARGET_H = 120, 70, 300, 2200


def analyser_sql(chemin):
    src = open(chemin).read()
    tables, fks = {}, []
    for m in re.finditer(r'CREATE TABLE (\w+)\.(\w+) \(\n(.*?)\n\);', src, re.S):
        sch, nom, corps = m.groups()
        cols, pk = [], []
        for ligne in corps.split('\n'):
            ligne = ligne.strip().rstrip(',')
            cm = re.match(r'CONSTRAINT \w+ PRIMARY KEY \(([^)]+)\)', ligne)
            if cm:
                pk = [c.strip() for c in cm.group(1).split(',')]
                continue
            if ligne.startswith('CONSTRAINT') or not ligne:
                continue
            cm = re.match(r'(\w+) (.+?)( NOT NULL)?( DEFAULT .*)?$', ligne)
            if cm:
                cols.append({'nom': cm.group(1), 'type': cm.group(2), 'nn': bool(cm.group(3)),
                             'defaut': (cm.group(4) or '').replace(' DEFAULT ', '')})
        tables[f'{sch}.{nom}'] = {'schema': sch, 'nom': nom, 'cols': cols, 'pk': pk,
                                  'x': 0, 'y': 0, 'comment': '', 'colcomments': {}}
    # tables sans schéma explicite (DDL "CREATE TABLE nom (")
    for m in re.finditer(r'CREATE TABLE (\w+) \(\n(.*?)\n\);', src, re.S):
        nom = m.group(1)
        if not any(t['nom'] == nom for t in tables.values()):
            pass  # rare : on ne gère que les DDL qualifiés pour l'instant
    for m in re.finditer(r"COMMENT ON TABLE (\w+)\.(\w+) IS E?'((?:[^']|'')*)'", src):
        cle = f'{m.group(1)}.{m.group(2)}'
        if cle in tables:
            tables[cle]['comment'] = m.group(3).replace("''", "'")
    for m in re.finditer(r"COMMENT ON COLUMN (\w+)\.(\w+)\.(\w+) IS E?'((?:[^']|'')*)'", src):
        cle = f'{m.group(1)}.{m.group(2)}'
        if cle in tables:
            tables[cle]['colcomments'][m.group(3)] = m.group(4).replace("''", "'")
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(\w+)\.(\w+)\s+ADD CONSTRAINT (\w+) FOREIGN KEY \((\w+)\)\s*'
            r'REFERENCES (\w+)\.(\w+)\s*\((\w+)\)', src):
        ssch, stab, cname, scol, dsch, dtab, dcol = m.groups()
        fks.append({'de': f'{ssch}.{stab}', 'col': scol, 'vers': f'{dsch}.{dtab}',
                    'colcible': dcol, 'nom': cname, 'audit': False})
    return tables, fks


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
    """Zones par schéma en bandeau, colonnes équilibrées, tables liées voisines."""
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
        resultat, vus = [], set()
        while len(vus) < len(cles):
            depart = max((c for c in cles if c not in vus), key=lambda c: (degre[c], c))
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


# Interface de la page générée : le gabarit est écrit en français, les autres
# langues sont des remplacements littéraux. Chaque clé doit exister telle
# quelle dans le gabarit — traduire() échoue sinon, pour détecter une dérive.
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
    },
}


def traduire(html, lang):
    if lang == 'fr':
        return html
    for source, cible in TRADUCTIONS[lang].items():
        if source not in html:
            sys.exit(f'traduction impossible : chaîne absente du gabarit : {source!r}')
        html = html.replace(source, cible)
    return html


def principal():
    ap = argparse.ArgumentParser(description="explorateur HTML interactif d'un modèle PostgreSQL")
    ap.add_argument('sql', help='fichier DDL PostgreSQL (CREATE TABLE...)')
    ap.add_argument('-o', '--sortie', help='fichier HTML produit (défaut : <sql>.html)')
    ap.add_argument('--titre', default=None, help="titre affiché (défaut : nom du fichier)")
    ap.add_argument('--dbm', help='modèle pgModeler pour reprendre les positions des tables')
    ap.add_argument('--fk-audit', default=None, metavar='REGEX',
                    help="regex des contraintes FK à classer « audit » (masquées par défaut)")
    ap.add_argument('--lang', default='fr', choices=['fr'] + sorted(TRADUCTIONS),
                    help="langue de l'interface de la page (défaut : fr)")
    args = ap.parse_args()

    tables, fks = analyser_sql(args.sql)
    if not tables:
        sys.exit('aucune table trouvée : le DDL doit contenir des CREATE TABLE schema.table')

    couleurs = {}
    if args.dbm:
        couleurs = positions_dbm(args.dbm, tables)
    if not args.dbm or all(t['x'] == 0 and t['y'] == 0 for t in tables.values()):
        placement_auto(tables, fks)

    schemas = sorted({t['schema'] for t in tables.values()})
    for i, s in enumerate(schemas):
        couleurs.setdefault(s, PALETTE[i % len(PALETTE)])

    if args.fk_audit:
        motif = re.compile(args.fk_audit)
        for f in fks:
            f['audit'] = bool(motif.search(f['nom']))

    titre = args.titre or Path(args.sql).stem
    sortie = args.sortie or str(Path(args.sql).with_suffix('.html'))
    donnees = {'schemas': couleurs, 'tables': list(tables.values()), 'fks': fks}
    json_txt = json.dumps(donnees, ensure_ascii=False).replace('</', '<\\/')

    ici = Path(__file__).parent
    html = (ici / 'templates' / 'explorateur.html').read_text()
    logo = (ici / 'logo.svg').read_text()
    html = traduire(html, args.lang)
    html = html.replace('__DONNEES__', json_txt).replace('__TITRE__', titre)
    html = html.replace('__LOGO__', logo.replace('width="128" height="128"', 'width="22" height="22"'))
    Path(sortie).write_text(html)
    naudit = sum(1 for f in fks if f['audit'])
    print(f'{len(tables)} tables, {len(fks)} FK'
          + (f" (dont {naudit} d'audit)" if naudit else '') + f' → {sortie}')


if __name__ == '__main__':
    principal()
