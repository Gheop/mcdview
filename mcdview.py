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
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
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


def identifiants(liste):
    """Split a comma list of column names and strip quoting, so PK/FK column
    names match the columns (which are stored unquoted)."""
    return [c.strip().strip('"`') for c in liste.split(',')]


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
    # the opening parenthesis may end the line or stand on its own. The body
    # is delimited by string search, not by a lazy `.*?` regex: on malformed
    # input (many openers, no closer) the latter backtracks catastrophically.
    for m in re.finditer(
            r'CREATE TABLE (?:IF NOT EXISTS )?(?:"?(\w+)"?\.)?"?(\w+)"?\s*\(\n', src):
        if ' PARTITION OF ' in src[m.start():m.end()]:
            continue
        fin = src.find('\n)', m.end())
        if fin == -1 or ';' not in src[fin:fin + 200]:
            continue
        corps = src[m.end():fin]
        if 'CREATE TABLE' in corps:  # opener with no closer: not a real body
            continue
        sch = m.group(1) or 'public'
        nom = m.group(2)
        cols, pk = [], []
        for ligne in corps.split('\n'):
            ligne = ligne.strip().rstrip(',')
            cm = re.match(r'(?:CONSTRAINT "?\w+"? )?PRIMARY KEY\s*\(([^)]+)\)', ligne)
            if cm:
                pk = identifiants(cm.group(1))
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
            r'ALTER TABLE (?:ONLY )?(?:"?(\w+)"?\.)?"?(\w+)"?\s+ADD CONSTRAINT "?\w+"?\s+'
            r'PRIMARY KEY\s*\(([^)]+)\)', src):
        cle = resoudre(f"{m.group(1) or 'public'}.{m.group(2)}")
        if cle in tables and not tables[cle]['pk']:
            tables[cle]['pk'] = identifiants(m.group(3))

    # columns added afterwards: ALTER TABLE t ADD [COLUMN] name type;
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:"?(\w+)"?\.)?"?(\w+)"?\s+ADD (?:COLUMN )?'
            r'(?!CONSTRAINT\b|PRIMARY\b|FOREIGN\b|UNIQUE\b|CHECK\b|INDEX\b|KEY\b|\()'
            r'["\[`]?(\w+)["\]`]?\s+([^;,\n]+)', src):
        cle = resoudre(f"{m.group(1) or 'public'}.{m.group(2)}")
        col = analyser_colonne(f"{m.group(3)} {m.group(4).strip()}")
        if cle in tables and col and col['nom'] not in {c['nom'] for c in tables[cle]['cols']}:
            tables[cle]['cols'].append(col)

    for m in re.finditer(r"COMMENT ON TABLE (?:\"?(\w+)\"?\.)?\"?(\w+)\"? IS E?'((?:[^']|'')*)'", src):
        cle = f"{m.group(1) or 'public'}.{m.group(2)}"
        if cle in tables:
            tables[cle]['comment'] = m.group(3).replace("''", "'")
    for m in re.finditer(r"COMMENT ON COLUMN (?:\"?(\w+)\"?\.)?\"?(\w+)\"?\.\"?(\w+)\"? IS E?'((?:[^']|'')*)'", src):
        cle = f"{m.group(1) or 'public'}.{m.group(2)}"
        if cle in tables:
            tables[cle]['colcomments'][m.group(3)] = m.group(4).replace("''", "'")

    # FKs, including composite ones, targets without columns (= target PK)
    # and declarations carried by partitions (folded back, then deduplicated)
    vues = set()
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:"?(\w+)"?\.)?"?(\w+)"?\s+ADD (?:CONSTRAINT "?(\w+)"?\s+)?'
            r'FOREIGN KEY\s*\(([^)]+)\)\s*REFERENCES (?:"?(\w+)"?\.)?"?(\w+)"?(?:\s*\(([^)]+)\))?',
            src):
        ssch, stab, cname, scols, dsch, dtab, dcols = m.groups()
        de = resoudre(f"{ssch or 'public'}.{stab}")
        vers = resoudre(f"{dsch or 'public'}.{dtab}")
        if de not in tables or vers not in tables:
            continue
        sources = identifiants(scols)
        cibles = (identifiants(dcols) if dcols
                  else tables[vers]['pk'])
        for i, scol in enumerate(sources):
            dcol = cibles[i] if i < len(cibles) else ''
            if (de, scol, vers, dcol) in vues:
                continue
            vues.add((de, scol, vers, dcol))
            fks.append({'de': de, 'col': scol, 'vers': vers,
                        'colcible': dcol, 'nom': cname or '', 'audit': False})
    return tables, fks


# non-PostgreSQL dialects go through sqlglot (optional dependency). PostgreSQL
# keeps the built-in regex parser, so the generator stays dependency-free by
# default; sqlglot only widens support when it is installed.
DIALECTES = ['auto', 'postgres', 'mysql', 'mariadb', 'sqlite', 'tsql',
             'oracle', 'duckdb', 'snowflake', 'bigquery', 'redshift',
             'clickhouse', 'trino', 'spark', 'hive']


def flairer_dialecte(chemin):
    src = open(chemin, errors='replace').read(300000)
    if 'AUTOINCREMENT' in src:
        return 'sqlite'
    if re.search(r'\[\w+\]\s+\w', src):
        return 'tsql'
    if re.search(r'CREATE TABLE[^(]*`', src):
        return 'mysql'
    return 'mysql'  # reasonable default for non-PostgreSQL DDL


# auto tries these sqlglot dialects (after the sniffed guess) and keeps the
# one that yields the most tables — one file is often only valid in one of them
DIALECTES_ESSAI = ['mysql', 'sqlite', 'postgres', 'tsql', 'oracle', 'clickhouse', 'duckdb']


def ressemble_postgres(chemin):
    """False when the DDL is clearly another dialect the regex parser would
    mangle: backticks (never valid PostgreSQL), AUTOINCREMENT (SQLite) or
    bracket-quoted identifiers like `[column] type` (SQL Server)."""
    src = open(chemin, errors='replace').read(300000)
    return ('`' not in src and 'AUTOINCREMENT' not in src.upper()
            and not re.search(r'\[\w+\]\s+\w', src))


def normaliser_casse(tables, fks):
    """Map PK/FK column names onto the actual column name when they differ only
    by case (unquoted SQL identifiers are case-insensitive), so the 🔑/🔗 icons
    match. A name with no case-insensitive match is left as is (a real phantom)."""
    for t in tables.values():
        reel = {c['nom'].lower(): c['nom'] for c in t['cols']}
        t['pk'] = [reel.get(p.lower(), p) for p in t['pk']]
    for f in fks:
        src = tables.get(f['de'])
        if src:
            f['col'] = {c['nom'].lower(): c['nom'] for c in src['cols']}.get(
                f['col'].lower(), f['col'])
        dst = tables.get(f['vers'])
        if dst and f['colcible']:
            f['colcible'] = {c['nom'].lower(): c['nom'] for c in dst['cols']}.get(
                f['colcible'].lower(), f['colcible'])
    return tables, fks


def analyser(chemin, dialecte='auto'):
    """Parse a DDL file. Returns (tables, fks, effective_dialect)."""
    if dialecte in ('postgres', 'postgresql'):
        tables, fks = analyser_sql(chemin)
        return (*normaliser_casse(tables, fks), 'postgresql')
    if dialecte == 'auto':
        # PostgreSQL regex parser first, but only trust it when the file isn't
        # obviously another dialect it would mis-parse (MySQL backtick PKs...)
        if ressemble_postgres(chemin):
            tables, fks = analyser_sql(chemin)
            if tables:
                return (*normaliser_casse(tables, fks), 'postgresql')
        # otherwise try several sqlglot dialects, keep the most tables
        candidats = list(dict.fromkeys([flairer_dialecte(chemin)] + DIALECTES_ESSAI))
        meilleur = ({}, [], candidats[0])
        for d in candidats:
            t, f = analyser_sqlglot(chemin, d, strict=False)
            if len(t) > len(meilleur[0]):
                meilleur = (t, f, d)
        return (*normaliser_casse(meilleur[0], meilleur[1]), meilleur[2])
    tables, fks = analyser_sqlglot(chemin, dialecte)
    return (*normaliser_casse(tables, fks), dialecte)


def analyser_sqlglot(chemin, dialecte, strict=True):
    try:
        import logging
        import sqlglot
        from sqlglot import expressions as exp
        from sqlglot.errors import ErrorLevel
        # quiet the per-statement "unsupported syntax, falling back" warnings
        logging.getLogger('sqlglot').setLevel(logging.ERROR)
    except ImportError:
        if not strict:
            return {}, []
        sys.exit(f'reading {dialecte} DDL needs sqlglot (pip install sqlglot)')
    try:
        # IGNORE: a single unparseable statement must not abort the whole model
        arbre = sqlglot.parse(open(chemin, errors='replace').read(),
                              read=dialecte, error_level=ErrorLevel.IGNORE)
    except Exception as e:
        if not strict:
            return {}, []
        sys.exit(f'sqlglot could not parse the DDL as {dialecte}: {e}')
    arbre = [s for s in arbre if s is not None]

    tables, fks = {}, []
    vues = set()

    def cle(tbl):
        return f"{tbl.db or 'public'}.{tbl.name}"

    def ajouter_fk(de, cols, ref, nom):
        cible = ref.find(exp.Table)
        if not cible:
            return
        vers = cle(cible)
        sch = ref.find(exp.Schema)
        cibles = [i.name for i in sch.expressions] if sch else []
        for i, col in enumerate(cols):
            dcol = cibles[i] if i < len(cibles) else ''
            if (de, col, vers, dcol) in vues:
                continue
            vues.add((de, col, vers, dcol))
            fks.append({'de': de, 'col': col, 'vers': vers,
                        'colcible': dcol, 'nom': nom or '', 'audit': False})

    for stmt in arbre:
        if isinstance(stmt, exp.Create) and stmt.kind == 'TABLE':
            noeud = stmt.this
            tbl = noeud.this if isinstance(noeud, exp.Schema) else noeud
            if not isinstance(tbl, exp.Table):
                continue
            k = cle(tbl)
            cols, pk, colcomments = [], [], {}
            for d in stmt.find_all(exp.ColumnDef):
                kinds = [c.kind for c in d.constraints]
                typ = d.args.get('kind')
                defc = next((c.this for c in kinds
                             if isinstance(c, exp.DefaultColumnConstraint)), None)
                comc = next((c.this for c in kinds
                             if isinstance(c, exp.CommentColumnConstraint)), None)
                if any(isinstance(c, exp.PrimaryKeyColumnConstraint) for c in kinds):
                    pk.append(d.name)
                for c in kinds:
                    if isinstance(c, exp.Reference):
                        ajouter_fk(k, [d.name], c, '')
                if comc is not None:
                    colcomments[d.name] = comc.name
                brut = typ.sql(dialect=dialecte) if typ else ''
                # lowercase to match the PostgreSQL parser's output, but keep
                # string literals intact (ENUM('Active') must not become 'active')
                type_txt = brut if "'" in brut else brut.lower()
                cols.append({'nom': d.name, 'type': type_txt,
                             'nn': any(isinstance(c, exp.NotNullColumnConstraint) for c in kinds),
                             'defaut': defc.sql(dialect=dialecte) if defc is not None else ''})
            for p in stmt.find_all(exp.PrimaryKey):
                noms = [c.name for c in p.expressions]
                if noms:
                    pk = noms
            comment = ''
            props = stmt.args.get('properties')
            for p in (props.expressions if props else []):
                if isinstance(p, exp.SchemaCommentProperty):
                    comment = p.this.name
            tables[k] = {'schema': tbl.db or 'public', 'nom': tbl.name, 'cols': cols,
                         'pk': pk, 'x': 0, 'y': 0, 'comment': comment,
                         'colcomments': colcomments}
            for fk in stmt.find_all(exp.ForeignKey):
                ref = fk.args.get('reference')
                if ref:
                    ajouter_fk(k, [c.name for c in fk.expressions], ref, fk.name)
        elif isinstance(stmt, exp.Alter):
            src_tbl = stmt.find(exp.Table)
            if src_tbl:
                for fk in stmt.find_all(exp.ForeignKey):
                    ref = fk.args.get('reference')
                    if ref:
                        ajouter_fk(cle(src_tbl), [c.name for c in fk.expressions], ref, fk.name)

    # a reference without a column list points at the target's primary key
    for f in fks:
        if not f['colcible']:
            pk = tables.get(f['vers'], {}).get('pk', [])
            if len(pk) == 1:
                f['colcible'] = pk[0]
    fks = [f for f in fks if f['de'] in tables and f['vers'] in tables]
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
    coin = Path(tempfile.mkdtemp(prefix='mcdview-'))
    sortie = coin / 'export.sql'

    def exporter(entree):
        return subprocess.run(['pgmodeler-cli', '--export-to-file', '--input',
                               entree, '--output', str(sortie), '--silent'],
                              capture_output=True, text=True)

    r = exporter(chemin)
    if r.returncode or not sortie.exists():
        # a .dbm from an older pgModeler often loads only after --fix-model
        repare = coin / 'repare.dbm'
        subprocess.run(['pgmodeler-cli', '--fix-model', '--input', chemin,
                        '--output', str(repare), '--silent'],
                       capture_output=True, text=True)
        # pgmodeler-cli 1.2.2 may segfault while freeing the model AFTER the
        # fixed file is fully written (memory-layout dependent: systematic in
        # containers, where the environment is tiny), so trust the output
        # file rather than the exit code; a truncated file fails the export.
        if repare.exists() and repare.stat().st_size:
            r = exporter(str(repare))
    if r.returncode or not sortie.exists():
        sys.exit(f'pgmodeler-cli export failed:\n{r.stdout}{r.stderr}')
    return str(sortie)


def sql_depuis_convertisseur(chemin, outil, cmd, format_nom, vers_stdout=False, env=None):
    """Run an external converter that turns a model file into PostgreSQL SQL,
    return the SQL path. Optional dependency, like pgmodeler-cli for .dbm.
    vers_stdout: the tool prints the SQL (captured) instead of writing sortie."""
    if not shutil.which(outil):
        sys.exit(f'reading a {format_nom} file requires {outil} in PATH')
    sortie = Path(tempfile.mkdtemp(prefix='mcdview-')) / 'export.sql'
    r = subprocess.run([a.format(entree=chemin, sortie=str(sortie)) for a in cmd],
                       capture_output=True, text=True, env=env)
    if vers_stdout and not r.returncode and r.stdout.strip():
        sortie.write_text(r.stdout)
    if r.returncode or not sortie.exists() or not sortie.stat().st_size:
        sys.exit(f'{outil} failed to convert the {format_nom} file:\n{r.stdout}{r.stderr}')
    return str(sortie)


def sql_depuis_dbml(chemin):
    """Convert a dbdiagram.io .dbml model to SQL through @dbml/cli (dbml2sql)."""
    return sql_depuis_convertisseur(
        chemin, 'dbml2sql',
        ['dbml2sql', '{entree}', '--postgres', '-o', '{sortie}'], 'DBML')


def sql_depuis_prisma(chemin):
    """Convert a Prisma schema to SQL through `prisma migrate diff` (writes to
    stdout). A dummy DATABASE_URL is set so `url = env(...)` schemas resolve;
    no database is contacted (--from-empty diffs against an empty datamodel)."""
    import os
    env = dict(os.environ, DATABASE_URL='postgresql://u:p@localhost:5432/d')
    return sql_depuis_convertisseur(
        chemin, 'prisma',
        ['prisma', 'migrate', 'diff', '--from-empty', '--to-schema-datamodel',
         '{entree}', '--script'], 'Prisma', vers_stdout=True, env=env)


def analyser_mwb(chemin):
    """Parse a MySQL Workbench .mwb model natively (zip + GRT XML, stdlib only).

    The .mwb is a zip whose document.mwb.xml is a GRT object tree: schemas hold
    tables, tables hold columns/indices/foreign keys, and cross-references
    (a column's type, a PK's columns, an FK's endpoints) are id links resolved
    against every object's `id` attribute.
    """
    with zipfile.ZipFile(chemin) as z:
        racine = ET.fromstring(z.read('document.mwb.xml'))

    def par_cle(el, cle):
        return next((c for c in el if c.get('key') == cle), None)

    def txt(el, cle):
        e = par_cle(el, cle)
        return (e.text or '').strip() if e is not None else ''

    def objets(el, cle):
        liste = par_cle(el, cle)
        return list(liste) if liste is not None else []

    def type_colonne(col):
        st = txt(col, 'simpleType') or txt(col, 'userType')
        base = st.rsplit('.', 1)[-1] if st else ''
        lg, prec, scale = txt(col, 'length'), txt(col, 'precision'), txt(col, 'scale')
        if lg and lg not in ('-1', '0'):
            return f'{base}({lg})'
        if prec and prec not in ('-1', '0'):
            return f'{base}({prec},{scale})' if scale and scale != '-1' else f'{base}({prec})'
        return base

    tables, fks = {}, []
    col_par_id = {}   # column id -> (name, table key)
    tbl_par_id = {}   # table id -> table key

    for sch in racine.iter('value'):
        if sch.get('struct-name') != 'db.mysql.Schema':
            continue
        schema = txt(sch, 'name') or 'public'
        for t in objets(sch, 'tables'):
            nom = txt(t, 'name')
            cle = f'{schema}.{nom}'
            tbl_par_id[t.get('id')] = cle
            cols = []
            for c in objets(t, 'columns'):
                cn = txt(c, 'name')
                col_par_id[c.get('id')] = (cn, cle)
                cols.append({'nom': cn, 'type': type_colonne(c),
                             'nn': txt(c, 'isNotNull') == '1', 'defaut': txt(c, 'defaultValue')})
            pk = []
            for idx in objets(t, 'indices'):
                if txt(idx, 'isPrimary') == '1':
                    for ic in objets(idx, 'columns'):
                        rc = txt(ic, 'referencedColumn')
                        if rc in col_par_id:
                            pk.append(col_par_id[rc][0])
            tables[cle] = {'schema': schema, 'nom': nom, 'cols': cols, 'pk': pk,
                           'x': 0, 'y': 0, 'comment': txt(t, 'comment'), 'colcomments': {}}

    for fk in racine.iter('value'):
        if fk.get('struct-name') != 'db.mysql.ForeignKey':
            continue
        srcs = [e.text.strip() for e in objets(fk, 'columns') if e.text]
        dsts = [e.text.strip() for e in objets(fk, 'referencedColumns') if e.text]
        cible_tbl = tbl_par_id.get(txt(fk, 'referencedTable'))
        nom = txt(fk, 'name')
        for i, scid in enumerate(srcs):
            if scid not in col_par_id:
                continue
            scol, de = col_par_id[scid]
            dcol, vers = col_par_id.get(dsts[i] if i < len(dsts) else None, ('', cible_tbl))
            vers = vers or cible_tbl
            if de in tables and vers in tables:
                fks.append({'de': de, 'col': scol, 'vers': vers,
                            'colcible': dcol, 'nom': nom, 'audit': False})
    return tables, fks


def singulariser(mot):
    """Rough ActiveRecord singularize, for the default FK column name."""
    if mot.endswith('ies'):
        return mot[:-3] + 'y'
    if re.search(r'(ss|sh|ch|x|z)es$', mot):
        return mot[:-2]
    if mot.endswith('s') and not mot.endswith('ss'):
        return mot[:-1]
    return mot


def analyser_schema_rb(chemin):
    """Parse a Rails db/schema.rb natively (the create_table / add_foreign_key
    DSL is regular). The implicit `id` primary key is added unless `id: false`;
    `add_foreign_key "from", "to"` defaults its column to <singular(to)>_id."""
    src = open(chemin, errors='replace').read()
    tables, fks = {}, []
    for m in re.finditer(
            r'create_table\s+["\']([^"\']+)["\']\s*(,[^\n]*?)?\s+do\s*\|(\w+)\|\n(.*?)\n\s*end',
            src, re.S):
        nom, opts, var, corps = m.groups()
        opts = opts or ''
        cle = f'public.{nom}'
        cols, pk = [], []
        if 'id: false' not in opts:
            mpk = re.search(r'primary_key:\s*["\']([^"\']+)["\']', opts)
            pkn = mpk.group(1) if mpk else 'id'
            mid = re.search(r'\bid:\s*:(\w+)', opts)
            cols.append({'nom': pkn, 'type': mid.group(1) if mid else 'bigint',
                         'nn': True, 'defaut': ''})
            pk = [pkn]
        for cm in re.finditer(r'\b' + re.escape(var) + r'\.(\w+)\s+["\'"]([^"\'"]+)["\'"]([^\n]*)', corps):
            typ, cn, reste = cm.groups()
            if typ == 'index':
                continue
            defc = re.search(r'default:\s*("[^"]*"|\'[^\']*\'|[^,\n]+)', reste)
            defaut = defc.group(1).strip('\'"') if defc else ''
            if typ in ('references', 'belongs_to'):
                cols.append({'nom': cn + '_id', 'type': 'bigint',
                             'nn': 'null: false' in reste, 'defaut': ''})
                if 'polymorphic: true' in reste:
                    cols.append({'nom': cn + '_type', 'type': 'string', 'nn': False, 'defaut': ''})
            else:
                cols.append({'nom': cn, 'type': typ, 'nn': 'null: false' in reste, 'defaut': defaut})
        tables[cle] = {'schema': 'public', 'nom': nom, 'cols': cols, 'pk': pk,
                       'x': 0, 'y': 0, 'comment': '', 'colcomments': {}}
    for m in re.finditer(r'add_foreign_key\s+["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']([^\n]*)', src):
        det, verst, reste = m.groups()
        mc = re.search(r'column:\s*["\']([^"\']+)["\']', reste)
        col = mc.group(1) if mc else singulariser(verst) + '_id'
        mp = re.search(r'primary_key:\s*["\']([^"\']+)["\']', reste)
        de, vers = f'public.{det}', f'public.{verst}'
        if de in tables and vers in tables:
            fks.append({'de': de, 'col': col, 'vers': vers,
                        'colcible': mp.group(1) if mp else 'id', 'nom': '', 'audit': False})
    return tables, fks


def analyser_mermaid(chemin):
    """Parse a Mermaid erDiagram natively (raw .mmd or inside a ```mermaid
    fence). Entities become tables, their attributes columns (PK marker → key);
    each relationship becomes an FK from the "many" side (crow's foot) to the
    "one" side — Mermaid does not name the FK column, so it is left blank."""
    src = open(chemin, errors='replace').read()
    d = src.find('erDiagram')
    if d == -1:
        return {}, []
    bloc = src[d + len('erDiagram'):]
    fin = bloc.find('\n```')
    if fin != -1:
        bloc = bloc[:fin]

    tables, fks = {}, []

    def table(nom):
        nom = nom.strip('"')
        cle = f'public.{nom}'
        if cle not in tables:
            tables[cle] = {'schema': 'public', 'nom': nom, 'cols': [], 'pk': [],
                           'x': 0, 'y': 0, 'comment': '', 'colcomments': {}}
        return cle

    # entity blocks: NAME { attr* }
    for m in re.finditer(r'(?:"([^"]+)"|([A-Za-z_][\w-]*))\s*\{(.*?)\}', bloc, re.S):
        nom = m.group(1) or m.group(2)
        cle = table(nom)
        for ligne in m.group(3).splitlines():
            am = re.match(r'\s*(\S+)\s+(\S+)((?:\s+(?:PK|FK|UK))*)', ligne)
            if not am:
                continue
            typ, cn, cles = am.groups()
            tables[cle]['cols'].append({'nom': cn, 'type': typ, 'nn': False, 'defaut': ''})
            if 'PK' in cles:
                tables[cle]['pk'].append(cn)

    # relationships: A <card>--|..<card> B : label
    masque = re.sub(r'(?:"[^"]+"|[A-Za-z_][\w-]*)\s*\{.*?\}', '', bloc, flags=re.S)
    for m in re.finditer(
            r'(?:"([^"]+)"|([A-Za-z_][\w-]*))\s+([|}o]{1,2})(?:--|\.\.)([|{o]{1,2})\s+'
            r'(?:"([^"]+)"|([A-Za-z_][\w-]*))', masque):
        gauche = m.group(1) or m.group(2)
        droite = m.group(5) or m.group(6)
        lcard, rcard = m.group(3), m.group(4)
        # the crow's foot ({ or }) marks the "many" side, which holds the FK
        if '{' in rcard:
            enfant, parent = droite, gauche
        elif '}' in lcard:
            enfant, parent = gauche, droite
        else:
            enfant, parent = droite, gauche
        de, vers = table(enfant), table(parent)
        cible = tables[vers]['pk'][0] if tables[vers]['pk'] else ''
        fks.append({'de': de, 'col': '', 'vers': vers, 'colcible': cible,
                    'nom': '', 'audit': False})
    return tables, fks


def analyser_drizzle(chemin):
    """Parse a Drizzle ORM schema.ts natively (regular enough): each
    `pgTable("name", { field: type("col").notNull().primaryKey()
    .references(() => other.col) })` becomes a table; `.references()` gives the
    foreign keys, resolved against the map of const-variable → table."""
    src = open(chemin, errors='replace').read()
    # drop comments so a commented-out table is not parsed (line comments only
    # at line start, to leave "https://" inside strings alone) and block ones
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'(?m)^\s*//.*$', '', src)
    tables, fks = {}, []
    var_table, var_cols = {}, {}   # const var -> table key / {field: column}
    refs = []                      # (de_key, src_col, target_var, target_field)

    def champs(body):              # split on top-level commas (depth 0)
        prof, cur, out = 0, '', []
        for ch in body:
            if ch in '([{':
                prof += 1
            elif ch in ')]}':
                prof -= 1
            if ch == ',' and prof == 0:
                out.append(cur); cur = ''
            else:
                cur += ch
        if cur.strip():
            out.append(cur)
        return out

    for m in re.finditer(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:pg|mysql|sqlite)Table\s*\(\s*'
            r'["\'`]([^"\'`]+)["\'`]\s*,\s*\{', src):
        var, nom = m.group(1), m.group(2)
        i, prof = m.end() - 1, 0    # scan balanced braces for the body
        while i < len(src):
            prof += (src[i] == '{') - (src[i] == '}')
            if prof == 0:
                break
            i += 1
        cle = f'public.{nom}'
        var_table[var] = cle
        var_cols[var] = {}
        cols, pk = [], []
        for entree in champs(src[m.end():i]):
            cm = re.match(r'\s*(\w+)\s*:\s*(\w+)\s*\(', entree)
            if not cm:
                continue
            champ, typ = cm.groups()
            sm = re.search(r'''["'`]([^"'`]+)["'`]''', entree)
            col = sm.group(1) if sm else champ
            var_cols[var][champ] = col
            cols.append({'nom': col, 'type': typ,
                         'nn': '.notNull(' in entree, 'defaut': ''})
            if '.primaryKey(' in entree:
                pk.append(col)
            rm = re.search(r'\.references\(\s*\(\s*\)\s*=>\s*(\w+)\.(\w+)', entree)
            if rm:
                refs.append((cle, col, rm.group(1), rm.group(2)))
        tables[cle] = {'schema': 'public', 'nom': nom, 'cols': cols, 'pk': pk,
                       'x': 0, 'y': 0, 'comment': '', 'colcomments': {}}

    for de, col, tvar, tfield in refs:
        vers = var_table.get(tvar)
        if de in tables and vers in tables:
            fks.append({'de': de, 'col': col, 'vers': vers,
                        'colcible': var_cols.get(tvar, {}).get(tfield, ''),
                        'nom': '', 'audit': False})
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
        cles_sch = ordonner(par_schema[sch])
        dims = {c: taille(tables[c]) for c in cles_sch}
        # column height aimed at a roughly square zone, so a schema with many
        # tables does not stretch into an unreadable 40:1 horizontal band;
        # max() keeps small schemas at the original TARGET_H
        haut_totale = sum(h + GAP_Y for w, h in dims.values())
        larg_moy = sum(w + GAP_X for w, h in dims.values()) / len(dims)
        cible_h = max(TARGET_H, (haut_totale * larg_moy) ** 0.5)
        col_x, col_w, y = zone_x, 0.0, 40.0
        max_x = zone_x
        for cle in cles_sch:
            w, h = dims[cle]
            if y > 40 and y + h > cible_h:
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
        '⇄ réorganiser': '⇄ rearrange',
        '"réétaler les tables pour dégager les liens"':
            '"spread the tables out to unclutter the links"',
        '"trop de tables pour réorganiser ("': '"too many tables to rearrange ("',
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


def echapper(texte):
    return (texte.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def url_sure(u):
    """Neutralize dangerous URL schemes (javascript:, data:...) in href values;
    http(s), mailto, anchors and scheme-less/relative URLs pass through."""
    if not u:
        return u
    schema = re.match(r'\s*([a-z][a-z0-9+.-]*):', u, re.I)
    if schema and schema.group(1).lower() not in ('http', 'https', 'mailto'):
        return '#'
    return u


MIMES_LOGO = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
              '.ico': 'image/x-icon'}


def composer_page(tables, fks, titre, lang='fr', couleurs=None, dialecte='postgresql',
                  home_url=None, logo_file=None, credit=None, credit_url=None):
    """Assemble the final HTML page from parsed and positioned tables."""
    couleurs = dict(couleurs or {})
    for i, s in enumerate(sorted({t['schema'] for t in tables.values()})):
        couleurs.setdefault(s, PALETTE[i % len(PALETTE)])
    donnees = {'schemas': couleurs, 'tables': list(tables.values()), 'fks': fks,
               'dialecte': dialecte}
    # '<' escaped in the JSON: no '</script>' or '<!--' can leak from the data
    json_txt = json.dumps(donnees, ensure_ascii=False).replace('<', '\\u003c')
    ici = Path(__file__).parent
    html = traduire((ici / 'templates' / 'explorateur.html').read_text(), lang)
    logo = (ici / 'logo.svg').read_text()
    html = html.replace('__DONNEES__', json_txt).replace('__TITRE__', echapper(titre))
    if logo_file:
        # a custom logo is embedded as <img> data URI: in an image context no
        # script from a third-party SVG can run, unlike an inlined <svg>
        mime = MIMES_LOGO.get(Path(logo_file).suffix.lower(), 'image/png')
        b64 = base64.b64encode(Path(logo_file).read_bytes()).decode()
        logo = f'<img src="data:{mime};base64,{b64}" width="22" height="22" alt="">'
    else:
        logo = logo.replace('width="128" height="128"', 'width="22" height="22"')
    if home_url:
        logo = (f'<a href="{echapper(url_sure(home_url))}" style="display:flex" '
                f'title="{echapper(url_sure(home_url))}">{logo}</a>')
    html = html.replace('__LOGO__', logo)

    # optional attribution stamp: the mcdview logo + caller-supplied text
    # (escaped), empty by default. The logo goes in as a data-URI <img> (no id
    # clash with the header SVG). mcdview-site passes its own; CLI users don't.
    badge = ''
    if credit:
        b64 = base64.b64encode((ici / 'logo.svg').read_bytes()).decode()
        contenu = (f'<img src="data:image/svg+xml;base64,{b64}" width="18" '
                   f'height="18" alt=""><b>{echapper(credit)}</b>')
        badge = (f'<a href="{echapper(url_sure(credit_url))}" target="_blank" '
                 f'rel="noopener">{contenu}</a>' if credit_url
                 else f'<span>{contenu}</span>')
    return html.replace('__CREDIT__', badge)


def principal():
    ap = argparse.ArgumentParser(description="interactive HTML explorer for a PostgreSQL data model")
    ap.add_argument('sql', metavar='sql|dbm|dbml|mwb|rb|mmd|ts',
                    help='SQL DDL, or a .dbm/.dbml/.mwb/.prisma model file')
    ap.add_argument('-o', '--sortie', help='output HTML file (default: <sql>.html)')
    ap.add_argument('--titre', default=None, help="displayed title (default: file name)")
    ap.add_argument('--dbm', help='pgModeler model to reuse table positions from')
    ap.add_argument('--fk-audit', default=None, metavar='REGEX',
                    help="regex of FK constraint names to tag as audit (hidden by default)")
    ap.add_argument('--lang', default='fr', choices=['fr'] + sorted(TRADUCTIONS),
                    help="language of the page UI (default: fr)")
    ap.add_argument('--dialect', default='auto', choices=DIALECTES,
                    help="input SQL dialect (default: auto; non-PostgreSQL needs sqlglot)")
    ap.add_argument('--home-url', default=None, metavar='URL',
                    help="wrap the header logo in a link to this URL")
    ap.add_argument('--logo', default=None, metavar='FILE',
                    help="replace the header logo (svg/png/jpg…, shown 22×22)")
    ap.add_argument('--credit', default=None, metavar='TEXT',
                    help="discreet attribution badge, bottom-right (off by default)")
    ap.add_argument('--credit-url', default=None, metavar='URL',
                    help="make the --credit badge a link to this URL")
    args = ap.parse_args()

    source = args.sql
    dialecte = args.dialect
    if source.endswith('.dbm'):
        if not args.dbm:
            args.dbm = source  # the model provides its own positions
        source = sql_depuis_dbm(source)
        dialecte = 'postgres'  # pgmodeler-cli always exports PostgreSQL
    elif source.endswith('.dbml'):
        source = sql_depuis_dbml(source)
        dialecte = 'postgres'  # dbml2sql emits PostgreSQL
    elif source.endswith('.prisma'):
        source = sql_depuis_prisma(source)
        # keep 'auto': prisma emits SQL in the schema's provider dialect
        # (postgres, mysql, sqlite, sqlserver), which auto detects
    if source.endswith('.mwb'):
        tables, fks = normaliser_casse(*analyser_mwb(source))
        dialecte = 'mysql'
    elif source.endswith('.rb'):
        tables, fks = normaliser_casse(*analyser_schema_rb(source))
        dialecte = 'rails'
    elif source.endswith(('.mmd', '.mermaid', '.md')):
        tables, fks = analyser_mermaid(source)
        dialecte = 'mermaid'
    elif source.endswith('.ts'):
        tables, fks = normaliser_casse(*analyser_drizzle(source))
        dialecte = 'drizzle'
    else:
        tables, fks, dialecte = analyser(source, dialecte)
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
    Path(sortie).write_text(composer_page(tables, fks, titre, args.lang, couleurs,
                                          dialecte, args.home_url, args.logo,
                                          args.credit, args.credit_url))
    naudit = sum(1 for f in fks if f['audit'])
    print(f'{len(tables)} tables, {len(fks)} FKs'
          + (f' (including {naudit} audit FKs)' if naudit else '') + f' → {sortie}')


if __name__ == '__main__':
    principal()
