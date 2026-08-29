#!/usr/bin/env python3
"""Schema diff: comparer() must tag every table, column and FK with the right
status (added / removed / changed / unchanged) and the page must render in diff
mode. Exits non-zero on a mismatch."""
import importlib.util
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)

# pg_dump style: a newline after "(", FKs as ALTER TABLE (both are what the
# PostgreSQL regex parser extracts)
VIEUX = """
CREATE TABLE client (
    id serial PRIMARY KEY,
    nom text
);
CREATE TABLE commande (
    id serial PRIMARY KEY,
    client_id int,
    total numeric
);
CREATE TABLE ancienne (
    id serial PRIMARY KEY,
    valeur text
);
ALTER TABLE ONLY commande ADD CONSTRAINT fk1 FOREIGN KEY (client_id) REFERENCES client(id);
"""
NEUF = """
CREATE TABLE client (
    id serial PRIMARY KEY,
    nom text,
    courriel text
);
CREATE TABLE commande (
    id serial PRIMARY KEY,
    client_id int,
    total bigint
);
CREATE TABLE ligne (
    id serial PRIMARY KEY,
    commande_id int
);
ALTER TABLE ONLY commande ADD CONSTRAINT fk1 FOREIGN KEY (client_id) REFERENCES client(id);
ALTER TABLE ONLY ligne ADD CONSTRAINT fk2 FOREIGN KEY (commande_id) REFERENCES commande(id);
"""


def modele(sql, td, nom):
    p = Path(td) / nom
    p.write_text(sql)
    return mcdview.analyser_sql(str(p))


def principal():
    import tempfile
    echecs = []
    with tempfile.TemporaryDirectory() as td:
        vieux = modele(VIEUX, td, 'v.sql')
        neuf = modele(NEUF, td, 'n.sql')
        tables, fks = mcdview.comparer(vieux, neuf)

    etat = {t['nom']: t.get('diff') for t in tables.values()}
    attendu = {'client': 'modifie', 'commande': 'modifie',
               'ligne': 'ajoute', 'ancienne': 'supprime'}
    for nom, veut in attendu.items():
        if etat.get(nom) != veut:
            echecs.append(f'table {nom}: diff {etat.get(nom)!r} != {veut!r}')

    cols = {t['nom']: {c['nom']: c.get('diff') for c in t['cols']}
            for t in tables.values()}
    if cols['client'].get('courriel') != 'ajoute':
        echecs.append('client.courriel devrait être ajoute')
    if cols['client'].get('nom') is not None:
        echecs.append('client.nom (inchangée) ne devrait pas être taggée')
    if cols['commande'].get('total') != 'modifie':  # numeric → bigint
        echecs.append('commande.total devrait être modifie (type changé)')
    if cols['ancienne'].get('valeur') != 'supprime':
        echecs.append('ancienne.valeur devrait être supprime')

    fkdiff = {(f['de'].split('.')[1], f['vers'].split('.')[1]): f.get('diff') for f in fks}
    if fkdiff.get(('ligne', 'commande')) != 'ajoute':
        echecs.append('FK ligne→commande devrait être ajoute')
    if fkdiff.get(('commande', 'client')) is not None:
        echecs.append('FK commande→client (inchangée) ne devrait pas être taggée')

    # the page renders in diff mode (the data island carries diff=True)
    mcdview.placement_auto(tables, fks)
    html = mcdview.composer_page(tables, fks, 'x', 'en', mode_diff=True)
    if '"diff": true' not in html:
        echecs.append('la page ne signale pas le mode diff')
    if 'id="filtreTouchees"' not in html:
        echecs.append('le bouton de filtre "touchées" manque de la page diff')

    # JSON summary for the hosting service
    r = mcdview.resume_diff(tables, fks, 'old.sql')
    ct = r['counts']['tables']
    if (ct['added'], ct['removed'], ct['changed']) != (1, 1, 2):
        echecs.append(f'résumé: comptes tables {ct} inattendus')
    prod = next((t for t in r['tables'] if t['table'] == 'public.commande'), None)
    total = next((c for c in (prod['columns'] if prod else []) if c['name'] == 'total'), None)
    if not total or total.get('was') != 'numeric':  # numeric → bigint
        echecs.append(f'résumé: type précédent de commande.total manquant ({total})')
    if r['counts']['foreign_keys']['added'] != 1:
        echecs.append('résumé: FK ajoutée non comptée')

    # rename detection: a table renamed (same column set) is not remove+add,
    # and a FK untouched apart from the rename stays unchanged
    av = "CREATE TABLE utilisateur (\n id serial PRIMARY KEY,\n nom text,\n mail text\n);\n"
    ap = "CREATE TABLE client (\n id serial PRIMARY KEY,\n nom text,\n mail text\n);\n"
    import tempfile as tf
    with tf.TemporaryDirectory() as td:
        rv = modele(av, td, 'rv.sql')
        rn = modele(ap, td, 'rn.sql')
    rt, rf = mcdview.comparer(rv, rn)
    noms = {t['nom']: t for t in rt.values()}
    if 'utilisateur' in noms:
        echecs.append('rename: ancienne table utilisateur émise (devrait être fusionnée)')
    if not noms.get('client') or noms['client'].get('renomme_de') != 'utilisateur':
        echecs.append('rename: client devrait porter renomme_de=utilisateur')

    if echecs:
        print('ÉCHECS diff :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('diff : tables/colonnes/FK taggées correctement, page en mode diff')


if __name__ == '__main__':
    principal()
