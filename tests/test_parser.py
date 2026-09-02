#!/usr/bin/env python3
"""PostgreSQL-parser edge cases that regressed or are easy to break: inline
column primary keys, and the phantom-PK traps a naive `PRIMARY KEY in line`
check falls into (a DEFAULT/CHECK/comment mentioning the words)."""
import importlib.util
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('mcdview', RACINE / 'mcdview.py')
mcdview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcdview)


def tables_de(sql):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'x.sql'
        p.write_text(sql)
        return dict(mcdview.analyser_sql(str(p))[0])


def fks_de(sql):
    """Return the FK set as {(de, col, vers, colcible)} (schemas stripped)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'x.sql'
        p.write_text(sql)
        return {(f['de'].split('.')[1], f['col'], f['vers'].split('.')[1],
                 f['colcible']) for f in mcdview.analyser_sql(str(p))[1]}


def principal():
    echecs = []

    # inline column PRIMARY KEY is detected and kept out of the type
    t = tables_de('CREATE TABLE public.a (\n id serial PRIMARY KEY,\n nom text\n);')
    a = t['public.a']
    if a['pk'] != ['id']:
        echecs.append(f'inline PK: pk={a["pk"]} != [id]')
    if next(c['type'] for c in a['cols'] if c['nom'] == 'id') != 'serial':
        echecs.append('inline PK: "PRIMARY KEY" a fui dans le type de id')

    # a DEFAULT / CHECK / comment mentioning "PRIMARY KEY" must NOT create a PK
    t = tables_de(
        "CREATE TABLE public.b (\n"
        "  id integer NOT NULL PRIMARY KEY,\n"
        "  status text DEFAULT 'PRIMARY KEY',\n"
        "  label text CHECK (label <> 'PRIMARY KEY'),\n"
        "  qty integer, -- was PRIMARY KEY once\n"
        "  note text\n);")
    if t['public.b']['pk'] != ['id']:
        echecs.append(f'phantom PK: pk={t["public.b"]["pk"]} != [id]')
    qty = next(c for c in t['public.b']['cols'] if c['nom'] == 'qty')
    if qty['type'] != 'integer':
        echecs.append(f'inline comment a fui dans le type: {qty["type"]!r}')

    # an ALTER-declared PK must win when a literal earlier said "PRIMARY KEY"
    t = tables_de(
        "CREATE TABLE public.c (\n  real_id integer NOT NULL,\n"
        "  code text DEFAULT 'PRIMARY KEY'\n);\n"
        "ALTER TABLE ONLY public.c ADD CONSTRAINT c_pk PRIMARY KEY (real_id);")
    if t['public.c']['pk'] != ['real_id']:
        echecs.append(f'ALTER PK écrasée par un faux inline: {t["public.c"]["pk"]}')

    # table-level PRIMARY KEY (col list) still works
    t = tables_de('CREATE TABLE public.d (\n a integer,\n b integer,\n'
                  ' PRIMARY KEY (a, b)\n);')
    if t['public.d']['pk'] != ['a', 'b']:
        echecs.append(f'PK composite table-level: {t["public.d"]["pk"]}')

    # a FK constraint wrapped across lines (pg_dump style) must not create a
    # phantom column named REFERENCES
    t = tables_de(
        'CREATE TABLE public.a (\n'
        '  id integer PRIMARY KEY,\n'
        '  b_id integer,\n'
        '  CONSTRAINT a_b_fkey FOREIGN KEY (b_id)\n'
        '      REFERENCES public.b (id)\n'
        ');')
    noms = [c['nom'] for c in t['public.a']['cols']]
    if 'REFERENCES' in noms or noms != ['id', 'b_id']:
        echecs.append(f'FK multi-ligne: colonnes={noms} (REFERENCES fantôme ?)')

    # FKs declared INSIDE the CREATE TABLE body (hand-written schemas): inline
    # column REFERENCES, table-level FOREIGN KEY (mono + composite), a
    # self-reference, and a column-less REFERENCES falling back to the target PK.
    got = fks_de(
        'CREATE TABLE employees (\n'
        '  id INT PRIMARY KEY,\n'
        '  manager_id INT REFERENCES employees(id)\n);\n'
        'CREATE TABLE orders (id INT PRIMARY KEY);\n'
        'CREATE TABLE products (id INT PRIMARY KEY);\n'
        'CREATE TABLE order_items (\n'
        '  order_id INT,\n  product_id INT,\n'
        '  PRIMARY KEY (order_id, product_id),\n'
        '  FOREIGN KEY (order_id) REFERENCES orders(id),\n'
        '  FOREIGN KEY (product_id) REFERENCES products(id)\n);')
    attendu = {('employees', 'manager_id', 'employees', 'id'),
               ('order_items', 'order_id', 'orders', 'id'),
               ('order_items', 'product_id', 'products', 'id')}
    if got != attendu:
        echecs.append(f'FK inline/table-level: {got} != {attendu}')

    # a composite table-level FK, and a column-less REFERENCES using the PK
    got = fks_de(
        'CREATE TABLE parent (\n a INT, b INT,\n PRIMARY KEY (a, b)\n);\n'
        'CREATE TABLE child (\n'
        '  pa INT, pb INT,\n  owner INT REFERENCES parent,\n'  # no target cols
        '  FOREIGN KEY (pa, pb) REFERENCES parent (a, b)\n);')
    attendu = {('child', 'pa', 'parent', 'a'), ('child', 'pb', 'parent', 'b'),
               ('child', 'owner', 'parent', 'a')}
    if got != attendu:
        echecs.append(f'FK composite/PK-fallback: {got} != {attendu}')

    # an inline FK and an ALTER FK for the same relation are not duplicated
    got = fks_de(
        'CREATE TABLE a (id INT PRIMARY KEY);\n'
        'CREATE TABLE b (\n id INT PRIMARY KEY,\n a_id INT REFERENCES a(id)\n);\n'
        'ALTER TABLE b ADD CONSTRAINT b_a FOREIGN KEY (a_id) REFERENCES a(id);')
    if got != {('b', 'a_id', 'a', 'id')}:
        echecs.append(f'FK dédup inline+ALTER: {got}')

    # single-line CREATE TABLE with an inline REFERENCES is caught too
    got = fks_de('CREATE TABLE a (id INT PRIMARY KEY);\n'
                 'CREATE TABLE b (id INT PRIMARY KEY, a_id INT REFERENCES a(id));')
    if got != {('b', 'a_id', 'a', 'id')}:
        echecs.append(f'FK inline single-line: {got}')

    # leading-comma DDL style (",\n  col TYPE"): columns, PK and table-level FK
    # must all parse despite the comma leading each entry
    t = tables_de(
        'CREATE TABLE zitadel.projects(\n'
        '    instance_id TEXT NOT NULL\n'
        '    , organization_id TEXT NOT NULL\n'
        '    , id TEXT NOT NULL\n'
        '    , PRIMARY KEY (instance_id, organization_id, id)\n);\n'
        'CREATE TABLE zitadel.project_roles(\n'
        '    instance_id TEXT NOT NULL\n'
        '    , organization_id TEXT NOT NULL\n'
        '    , project_id TEXT NOT NULL\n'
        '    , key TEXT NOT NULL\n'
        '    , PRIMARY KEY (instance_id, project_id, key)\n'
        '    , FOREIGN KEY (instance_id, organization_id, project_id)'
        ' REFERENCES zitadel.projects(instance_id, organization_id, id)\n);')
    pr = t['zitadel.project_roles']
    if [c['nom'] for c in pr['cols']] != ['instance_id', 'organization_id', 'project_id', 'key']:
        echecs.append(f'virgule en tête: colonnes={[c["nom"] for c in pr["cols"]]}')
    if pr['pk'] != ['instance_id', 'project_id', 'key']:
        echecs.append(f'virgule en tête: PK={pr["pk"]}')
    got = fks_de(
        'CREATE TABLE p(\n  id TEXT NOT NULL\n  , PRIMARY KEY (id)\n);\n'
        'CREATE TABLE c(\n  pid TEXT\n  , FOREIGN KEY (pid) REFERENCES p(id)\n);')
    if got != {('c', 'pid', 'p', 'id')}:
        echecs.append(f'virgule en tête FK: {got}')

    # a CREATE TABLE whose "(" is followed by columns on the SAME line and whose
    # body continues on later lines (closing ")" elsewhere) must parse even in a
    # mixed file — previously the built-in parser dropped it (no sqlglot fallback
    # once another table had parsed)
    t = tables_de(
        'CREATE TABLE users (id INT PRIMARY KEY, name TEXT);\n'
        'CREATE TABLE posts (id INT PRIMARY KEY, user_id INT,\n'
        '  FOREIGN KEY (user_id) REFERENCES users(id));')
    if 'public.posts' not in t or [c['nom'] for c in t.get('public.posts', {}).get('cols', [])] != ['id', 'user_id']:
        echecs.append(f'ouverture inline multi-ligne: posts={t.get("public.posts")}')
    got = fks_de(
        'CREATE TABLE users (id INT PRIMARY KEY, name TEXT);\n'
        'CREATE TABLE posts (id INT PRIMARY KEY, user_id INT,\n'
        '  FOREIGN KEY (user_id) REFERENCES users(id));')
    if got != {('posts', 'user_id', 'users', 'id')}:
        echecs.append(f'ouverture inline multi-ligne FK: {got}')

    # single-line / compact CREATE TABLE (no newline after the open paren) is
    # parsed by the built-in parser, not only via sqlglot
    t = tables_de("CREATE TABLE t (a integer PRIMARY KEY, b numeric(10,2), c text);")
    tt = t.get('public.t', {})
    noms = [c['nom'] for c in tt.get('cols', [])]
    if noms != ['a', 'b', 'c'] or tt.get('pk') != ['a']:
        echecs.append(f'single-line: cols={noms} pk={tt.get("pk")}')
    typ_b = next((c['type'] for c in tt.get('cols', []) if c['nom'] == 'b'), None)
    if typ_b != 'numeric(10,2)':  # comma inside the type must not split
        echecs.append(f'single-line: type de b = {typ_b!r} (numeric(10,2) attendu)')
    # a comma/paren inside a string literal must not split the body
    t = tables_de("CREATE TABLE u (a text DEFAULT 'x,(y)', b integer);")
    if [c['nom'] for c in t.get('public.u', {}).get('cols', [])] != ['a', 'b']:
        echecs.append('single-line: littéral avec ,/() a cassé le découpage')

    # indexes and unique constraints are extracted
    t = tables_de(
        'CREATE TABLE public.e (\n id serial PRIMARY KEY,\n email text\n);\n'
        'CREATE UNIQUE INDEX e_email ON public.e (email);\n'
        'CREATE INDEX e_id ON public.e (id);')
    idx = {i['nom']: i for i in t['public.e']['index']}
    if idx.get('e_email', {}).get('unique') is not True or idx.get('e_id', {}).get('unique') is not False:
        echecs.append(f'index: extraction inattendue ({list(idx)})')

    # several input files are merged into one model, cross-file FKs resolved
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        Path(td, 'a.sql').write_text('CREATE TABLE client (\n id serial PRIMARY KEY\n);')
        Path(td, 'b.sql').write_text(
            'CREATE TABLE commande (\n id serial PRIMARY KEY,\n client_id integer\n);\n'
            'ALTER TABLE ONLY commande ADD CONSTRAINT fk '
            'FOREIGN KEY (client_id) REFERENCES client(id);')
        out = Path(td, 'm.html')
        r = subprocess.run(
            [sys.executable, str(RACINE / 'mcdview.py'),
             str(Path(td, 'a.sql')), str(Path(td, 'b.sql')), '-o', str(out)],
            capture_output=True, text=True)
        if '2 tables, 1 FKs' not in r.stdout:
            echecs.append(f'merge multi-fichiers: {r.stdout.strip()!r} (attendu 2 tables, 1 FK)')

    # --diagnose emits JSON and never fails (exit 0), whatever the input
    import json as _json
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        bon = Path(td) / 'a.sql'
        bon.write_text('CREATE TABLE t (\n a integer PRIMARY KEY,\n b text\n);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'),
                            str(bon), '--diagnose'], capture_output=True, text=True)
        d = _json.loads(r.stdout)
        if r.returncode != 0 or d['status'] != 'ok' or d['tables'] != 1:
            echecs.append(f'--diagnose ok: {r.returncode} {d.get("status")}')
        mauvais = Path(td) / 'b.mwb'
        mauvais.write_text('not a zip')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'),
                            str(mauvais), '--diagnose'], capture_output=True, text=True)
        d = _json.loads(r.stdout)
        if r.returncode != 0 or d['status'] != 'error':
            echecs.append(f'--diagnose error: exit={r.returncode} status={d.get("status")}')
        # several tables and no FK: soft "disconnected_tables" anomaly
        sansfk = Path(td) / 'c.sql'
        sansfk.write_text('CREATE TABLE a (id int);\nCREATE TABLE b (id int);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'),
                            str(sansfk), '--diagnose'], capture_output=True, text=True)
        d = _json.loads(r.stdout)
        if d['status'] != 'anomaly' or d['anomalies']['disconnected_tables'] != 2:
            echecs.append(f'--diagnose disconnected: status={d.get("status")} '
                          f'anom={d.get("anomalies")}')

    # --lint: rule violations + --fail-on exit code
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'a.sql'
        f.write_text('CREATE TABLE Users (id INT PRIMARY KEY, Name TEXT);\n'
                     'CREATE TABLE posts (\n  id INT PRIMARY KEY,\n  user_id INT,\n'
                     '  FOREIGN KEY (user_id) REFERENCES Users(id)\n);\n'
                     'CREATE TABLE logs (msg TEXT);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f), '--lint'],
                           capture_output=True, text=True)
        d = _json.loads(r.stdout)
        regles = d['counts']
        for attendu in ('missing_pk', 'disconnected_table', 'unindexed_fk', 'naming_case'):
            if attendu not in regles:
                echecs.append(f'--lint: règle {attendu} manquante ({regles})')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f),
                            '--lint', '--fail-on', 'warning'], capture_output=True, text=True)
        if r.returncode != 1:
            echecs.append(f'--lint --fail-on warning: exit {r.returncode} (attendu 1)')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f),
                            '--lint', '--fail-on', 'error'], capture_output=True, text=True)
        if r.returncode != 0:
            echecs.append(f'--lint --fail-on error: exit {r.returncode} (attendu 0)')

    # --to-dico: a Markdown data dictionary with a column/type/key table
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'a.sql'
        f.write_text('CREATE TABLE client (id serial PRIMARY KEY, nom text NOT NULL);\n'
                     'CREATE TABLE commande (\n  id serial PRIMARY KEY,\n  client_id integer,\n'
                     '  FOREIGN KEY (client_id) REFERENCES client(id)\n);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f), '--to-dico'],
                           capture_output=True, text=True)
        md = r.stdout
        if ('## public.client' not in md or '## public.commande' not in md
                or '| column | type | key |' not in md
                or '| id | serial | PK |' not in md
                or '| client_id | integer | FK → commande |' in md  # target, not source
                or 'FK → client' not in md or 'NOT NULL' not in md):
            echecs.append(f'--to-dico: sortie inattendue ({md[:200]!r})')

    # --to-preview: a valid standalone SVG naming the tables
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'a.sql'
        f.write_text('CREATE TABLE client (id serial PRIMARY KEY, nom text);\n'
                     'CREATE TABLE commande (\n  id serial PRIMARY KEY,\n  client_id integer,\n'
                     '  FOREIGN KEY (client_id) REFERENCES client(id)\n);')
        r = subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f), '--to-preview'],
                           capture_output=True, text=True)
        svg = r.stdout
        import xml.dom.minidom as _xml
        try:
            _xml.parseString(svg)
        except Exception as e:
            echecs.append(f'--to-preview: SVG invalide ({e})')
        if '<svg' not in svg or 'client' not in svg or 'commande' not in svg:
            echecs.append('--to-preview: SVG sans <svg> ou sans les tables')

    # attribution stamp: on by default, off with --no-credit, custom with
    # --credit; composer_page(tampon=False) lets the official site drop it
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / 'a.sql'
        f.write_text('CREATE TABLE t (id int PRIMARY KEY);')
        o = Path(td) / 'd.html'

        def gen(*extra):
            subprocess.run([sys.executable, str(RACINE / 'mcdview.py'), str(f),
                            '-o', str(o), *extra], capture_output=True, text=True)
            return o.read_text()

        if '<b>mcdview</b>' not in gen():
            echecs.append('stamp: absent by default (should be on)')
        if '<b>mcdview</b>' in gen('--no-credit'):
            echecs.append('stamp: still present with --no-credit')
        h = gen('--credit', 'Maison')
        if '<b>Maison</b>' not in h or '<b>mcdview</b>' in h:
            echecs.append('stamp: --credit did not override the default text')
        tbl, fkl = mcdview.analyser_sql(str(f))
        if '<b>mcdview</b>' in mcdview.composer_page(tbl, fkl, 'x', tampon=False):
            echecs.append('stamp: composer_page(tampon=False) still stamped')
        if '<b>mcdview</b>' not in mcdview.composer_page(tbl, fkl, 'x'):
            echecs.append('stamp: composer_page default did not stamp')

    if echecs:
        print('ÉCHECS parser :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('parser : PK inline, pas de PK fantôme, merge multi-fichiers OK')


if __name__ == '__main__':
    principal()
