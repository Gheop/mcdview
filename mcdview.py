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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path


def version_mcdview():
    """The single source of truth is pyproject.toml. When installed, read it
    from the package metadata; in a source checkout, from the sibling file."""
    try:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return version('mcdview')
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    try:
        txt = (Path(__file__).parent / 'pyproject.toml').read_text()
        m = re.search(r'^version\s*=\s*"([^"]+)"', txt, re.M)
        if m:
            return m.group(1)
    except Exception:
        pass
    return 'unknown'


PALETTE = ['#cdebc5', '#d6e6f5', '#a8d8b9', '#f5e3c8', '#e8d5f0',
           '#f0d0d0', '#d0e8e8', '#ede5c0', '#dcd6f7', '#f5d6a6']

# automatic-layout metrics (same orders of magnitude as the CSS rendering)
CHAR_W, ROW_H, HDR_H = 7.6, 20.5, 34
GAP_X, GAP_Y, ZONE_GAP = 120, 70, 300


# keywords opening a constraint line inside a CREATE TABLE body
MOTS_CONTRAINTE = ('CONSTRAINT', 'PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE',
                   'CHECK', 'EXCLUDE', 'LIKE ',
                   # a FK constraint often wraps: "... FOREIGN KEY (x)\n
                   # REFERENCES t (y)"; the continuation line must not be read
                   # as a column named REFERENCES
                   'REFERENCES ', 'REFERENCES(')


RE_COLONNE = re.compile(r'"?(\w+)"?\s+(.+)$')
RE_NOT_NULL = re.compile(r'\s*\bNOT NULL\b')
RE_DEFAUT = re.compile(r'\s*\bDEFAULT\s+(.*)$')
RE_COUPE = re.compile(r'\s+\b(?:REFERENCES|GENERATED|COLLATE|CONSTRAINT|PRIMARY|UNIQUE|CHECK)\b')
RE_PK_TABLE = re.compile(r'(?:CONSTRAINT "?\w+"? )?PRIMARY KEY\s*\(([^)]+)\)')
# FKs declared inside a CREATE TABLE body (pg_dump uses ALTER TABLE instead, but
# hand-written schemas embed them): a table-level FOREIGN KEY (...) REFERENCES,
# and a column-level inline REFERENCES. Both may carry a target column list or
# lean on the target PK, and either can be self-referential.
RE_FK_TABLE = re.compile(
    r'(?:CONSTRAINT\s+"?\w+"?\s+)?FOREIGN\s+KEY\s*\(([^)]+)\)\s*'
    r'REFERENCES\s+(?:"?(\w+)"?\.)?"?(\w+)"?(?:\s*\(([^)]+)\))?', re.I)
RE_FK_INLINE = re.compile(
    r'\bREFERENCES\s+(?:"?(\w+)"?\.)?"?(\w+)"?(?:\s*\(([^)]+)\))?', re.I)
# an entry that opens with a table constraint keyword is not a column definition
RE_DEBUT_CONTRAINTE = re.compile(
    r'^\s*(?:CONSTRAINT\s+"?\w+"?\s+)?'
    r'(?:PRIMARY|FOREIGN|UNIQUE|CHECK|EXCLUDE|LIKE)\b', re.I)


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
    reste = re.sub(r'--.*$', '', reste)  # an inline comment is not part of the type
    # cut what we do not represent (inline REFERENCES, GENERATED, COLLATE...)
    reste = RE_COUPE.split(reste)[0]
    return nouvelle_colonne(nom, reste.strip().rstrip(',').strip(), nn, defaut)


def ressource(rel):
    """Locate a bundled data file (the HTML template, the logo). In a source
    checkout it sits next to this file; a pip/pipx install carries it under
    `_assets/` alongside the module (see pyproject force-include)."""
    ici = Path(__file__).parent
    for base in (ici, ici / '_assets'):
        p = base / rel
        if p.exists():
            return p
    return ici / rel  # let the caller's read() raise a clear FileNotFoundError


def nouvelle_table(schema, nom, cols=None, pk=None, comment='', colcomments=None,
                   index=None):
    """The table record every parser produces and composer_page consumes — one
    place to evolve its shape (x/y are filled in later by the layout). `index`
    holds unique/index constraints as {'nom', 'cols', 'unique'} (PostgreSQL)."""
    return {'schema': schema, 'nom': nom,
            'cols': cols if cols is not None else [],
            'pk': pk if pk is not None else [],
            'x': 0, 'y': 0, 'comment': comment,
            'colcomments': colcomments if colcomments is not None else {},
            'index': index if index is not None else []}


def nouvelle_colonne(nom, typ, nn=False, defaut=''):
    return {'nom': nom, 'type': typ, 'nn': nn, 'defaut': defaut}


def nouvelle_fk(de, col, vers, colcible, nom=''):
    """The foreign-key record every parser produces (one line from `de.col` to
    `vers.colcible`); `nom` is the constraint name, used only by --fk-audit."""
    return {'de': de, 'col': col, 'vers': vers, 'colcible': colcible,
            'nom': nom, 'audit': False}


RE_LITTERAL = re.compile(r"'(?:[^']|'')*'")
RE_COMMENTAIRE = re.compile(r'--.*$')
RE_CHECK = re.compile(r'\bCHECK\s*\([^)]*\)', re.I)
RE_PK_MOT = re.compile(r'\bPRIMARY\s+KEY\b', re.I)


def colonne_declare_pk(ligne):
    """True if a column line carries a column-level PRIMARY KEY constraint.
    String literals, inline comments and CHECK(...) expressions are stripped
    first, so a DEFAULT 'PRIMARY KEY', a `-- primary key` note or a
    CHECK (x <> 'PRIMARY KEY') never counts as one. Cheap substring guard
    first: the vast majority of column lines have no PRIMARY KEY at all."""
    if 'primary' not in ligne.lower():
        return False
    s = RE_LITTERAL.sub('', ligne)     # drop '...' string literals
    s = RE_COMMENTAIRE.sub('', s)      # drop an inline comment
    s = RE_CHECK.sub('', s)            # drop CHECK(...)
    return bool(RE_PK_MOT.search(s))


def entrees_en_table(sch, nom, entrees):
    """Build a table record from the CREATE TABLE body split into entries (one
    per column or table constraint). Same logic whether an entry came from a
    line (multi-line DDL) or a top-level comma (single-line DDL)."""
    cols, pk = [], []
    for e in entrees:
        # strip a separating comma at EITHER end: leading-comma DDL style
        # (",\n  col TYPE") is common in hand-written schemas, and left the
        # comma glued to the column/constraint so it parsed as neither
        e = e.strip().strip(',').strip()
        cm = RE_PK_TABLE.match(e) if 'PRIMARY' in e else None
        if cm:
            pk = identifiants(cm.group(1))
            continue
        if not e or e.startswith('--') or e.startswith(MOTS_CONTRAINTE):
            continue
        col = analyser_colonne(e)
        if col:
            # a column-level PRIMARY KEY is not a separate constraint entry;
            # catch it here, but only as a real constraint (not a
            # literal/comment/CHECK that merely says "PRIMARY KEY")
            if colonne_declare_pk(e):
                pk.append(col['nom'])
            cols.append(col)
    return nouvelle_table(sch, nom, cols, pk)


def decouper_corps(s, cap=100000):
    """Split a CREATE TABLE body (the text right after the opening paren) into
    top-level entries, stopping at the matching close paren. Depth-counted and
    string-aware so a comma or paren inside numeric(10,2) or a 'literal' does
    not split. Linear scan, bounded by `cap`, no regex — safe on hostile input.
    Returns (entries, matched) where matched is True if the close paren was
    found."""
    entrees, cur, prof, en_chaine, i = [], [], 0, False, 0
    n = min(len(s), cap)
    while i < n:
        c = s[i]
        if en_chaine:
            cur.append(c)
            if c == "'":
                if i + 1 < n and s[i + 1] == "'":
                    cur.append("'")
                    i += 2
                    continue
                en_chaine = False
            i += 1
            continue
        if c == "'":
            en_chaine = True
            cur.append(c)
        elif c == '(':
            prof += 1
            cur.append(c)
        elif c == ')':
            if prof == 0:
                entrees.append(''.join(cur))
                return entrees, True
            prof -= 1
            cur.append(c)
        elif c == ',' and prof == 0:
            entrees.append(''.join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    return entrees, False


def analyser_sql(chemin):
    src = open(chemin).read()
    tables, fks = {}, []
    corps_par_cle = {}   # cle -> raw CREATE TABLE body, for inline/table-level FKs

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
        tables[f'{sch}.{nom}'] = entrees_en_table(sch, nom, corps.split('\n'))
        corps_par_cle[f'{sch}.{nom}'] = corps

    # single-line / compact CREATE TABLE (open paren NOT followed by a newline):
    # the fast pass above needs "(\n", so a one-line "CREATE TABLE t (a int);"
    # would otherwise only parse through sqlglot. Handle it here, bounded to the
    # opener's own line so a "CREATE TABLE a (\n" bomb (newline right after the
    # paren) yields an empty body and costs nothing.
    for m in re.finditer(
            r'CREATE TABLE (?:IF NOT EXISTS )?(?:"?(\w+)"?\.)?"?(\w+)"?\s*\(', src):
        cle = f"{m.group(1) or 'public'}.{m.group(2)}"
        if cle in tables:  # already built by the multi-line pass
            continue
        # slice only to the end of the opener's line, not the whole remaining
        # file (else 3000 unterminated openers each copy the full tail — a DoS)
        fin_ligne = src.find('\n', m.end())
        ligne_reste = src[m.end():fin_ligne if fin_ligne != -1 else len(src)]
        entrees, ok = decouper_corps(ligne_reste)
        if ok and entrees:
            tables[cle] = entrees_en_table(m.group(1) or 'public', m.group(2), entrees)
            corps_par_cle[cle] = ligne_reste

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

    # indexes and unique constraints (pg_dump emits CREATE [UNIQUE] INDEX;
    # ALTER TABLE ADD CONSTRAINT ... UNIQUE covers unique keys)
    for m in re.finditer(
            r'CREATE\s+(UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF NOT EXISTS\s+)?'
            r'"?(\w+)"?\s+ON\s+(?:ONLY\s+)?(?:"?(\w+)"?\.)?"?(\w+)"?[^(;]*\(([^)]+)\)', src):
        cle = resoudre(f"{m.group(3) or 'public'}.{m.group(4)}")
        if cle in tables:
            tables[cle]['index'].append(
                {'nom': m.group(2), 'cols': identifiants(m.group(5)),
                 'unique': bool(m.group(1))})
    for m in re.finditer(
            r'ALTER TABLE (?:ONLY )?(?:"?(\w+)"?\.)?"?(\w+)"?\s+ADD CONSTRAINT '
            r'"?(\w+)"?\s+UNIQUE\s*\(([^)]+)\)', src):
        cle = resoudre(f"{m.group(1) or 'public'}.{m.group(2)}")
        if cle in tables:
            tables[cle]['index'].append(
                {'nom': m.group(3), 'cols': identifiants(m.group(4)), 'unique': True})

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
            fks.append(nouvelle_fk(de, scol, vers, dcol, cname or ''))

    # FKs embedded in the CREATE TABLE body (hand-written schemas): a column-level
    # inline `col type REFERENCES tgt(id)` and a table-level `FOREIGN KEY (...)
    # REFERENCES tgt(...)`, mono or composite, possibly self-referential. Scanned
    # on the stored bodies once every table exists (so a column-less REFERENCES
    # can fall back to the target PK), deduplicated against the ALTER pass above.
    def ajouter_fk(de, scol, vers, dcol, nom):
        if (de, scol, vers, dcol) in vues:
            return
        vues.add((de, scol, vers, dcol))
        fks.append(nouvelle_fk(de, scol, vers, dcol, nom))

    for cle, corps in corps_par_cle.items():
        de = resoudre(cle)
        if de not in tables:
            continue
        # terminate the body so decouper_corps emits the final entry too (it only
        # flushes the buffer at a depth-0 ')' or comma; a multi-line body has
        # neither after its last column, and a single-line one stops at its real
        # close paren before this added one)
        entrees, _ = decouper_corps(corps + '\n)')
        for e in entrees:
            e = RE_COMMENTAIRE.sub('', RE_LITTERAL.sub('', e)).strip()
            mt = RE_FK_TABLE.match(e)
            if mt:
                scols, dsch, dtab, dcols = mt.groups()
                sources = identifiants(scols)
            elif RE_DEBUT_CONTRAINTE.match(e):
                continue  # a non-FK table constraint (PK/UNIQUE/CHECK…)
            else:
                cm = RE_COLONNE.match(e)
                mi = RE_FK_INLINE.search(e) if cm else None
                if not mi:
                    continue
                dsch, dtab, dcols = mi.groups()
                sources = [cm.group(1).strip('"`')]
            vers = resoudre(f"{dsch or 'public'}.{dtab}")
            if vers not in tables:
                continue
            cibles = identifiants(dcols) if dcols else tables[vers]['pk']
            for i, scol in enumerate(sources):
                ajouter_fk(de, scol, vers, cibles[i] if i < len(cibles) else '', '')
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
    return 'mysql'  # backticks or anything else: MySQL is the sensible default


# auto tries these sqlglot dialects (after the sniffed guess) and keeps the
# one that yields the most tables — one file is often only valid in one of them
DIALECTES_ESSAI = ['mysql', 'sqlite', 'postgres', 'tsql', 'oracle', 'clickhouse', 'duckdb']
# above this size, --dialect auto picks the dialect on a prefix, then does one
# full parse with the winner — instead of a full sqlglot parse per candidate
# dialect. A ~25 KB prefix already distinguishes dialects by table count.
SEUIL_ECHANTILLON = 25000


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
        # otherwise try several sqlglot dialects, keep the most tables. Each
        # try is a full sqlglot parse (O(size)); on a big file, pick the
        # dialect on a bounded prefix, then parse it in full just once.
        candidats = list(dict.fromkeys([flairer_dialecte(chemin)] + DIALECTES_ESSAI))
        src = open(chemin, errors='replace').read()

        def essayer(d, texte):
            # defense in depth: an unforeseen sqlglot AST shape must not crash
            # the whole tool — fall back to no tables for that dialect
            try:
                return analyser_sqlglot(chemin, d, False, texte)
            except Exception:
                return {}, []

        if len(src) > SEUIL_ECHANTILLON:
            ech = src[:SEUIL_ECHANTILLON]
            d = max(candidats, key=lambda d: len(essayer(d, ech)[0]))
            return (*normaliser_casse(*essayer(d, src)), d)
        meilleur = ({}, [], candidats[0])
        for d in candidats:
            t, f = essayer(d, src)
            if len(t) > len(meilleur[0]):
                meilleur = (t, f, d)
        return (*normaliser_casse(meilleur[0], meilleur[1]), meilleur[2])
    tables, fks = analyser_sqlglot(chemin, dialecte)
    return (*normaliser_casse(tables, fks), dialecte)


def analyser_sqlglot(chemin, dialecte, strict=True, src=None):
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
    if src is None:
        src = open(chemin, errors='replace').read()
    try:
        # IGNORE: a single unparseable statement must not abort the whole model
        arbre = sqlglot.parse(src, read=dialecte, error_level=ErrorLevel.IGNORE)
    except Exception as e:
        if not strict:
            return {}, []
        sys.exit(f'sqlglot could not parse the DDL as {dialecte}: {e}')
    arbre = [s for s in arbre if s is not None]

    tables, fks = {}, []
    vues = set()

    def cle(tbl):
        return f"{tbl.db or 'public'}.{tbl.name}"

    def nom_fk(fk):
        # a named inline FK carries its name on the wrapping Constraint node,
        # not on the ForeignKey itself
        if not fk.name and isinstance(fk.parent, exp.Constraint):
            return fk.parent.name
        return fk.name

    def rendre_sql(noeud):
        # sqlglot's generator itself can crash on some exotic default/type
        # expressions; a rendering failure must not abort the whole parse
        try:
            return noeud.sql(dialect=dialecte)
        except Exception:
            return ''

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
            fks.append(nouvelle_fk(de, col, vers, dcol, nom or ''))

    for stmt in arbre:
        if isinstance(stmt, exp.Create) and stmt.kind == 'TABLE':
            noeud = stmt.this
            tbl = noeud.this if isinstance(noeud, exp.Schema) else noeud
            if not isinstance(tbl, exp.Table):
                continue
            k = cle(tbl)
            cols, pk, colcomments = [], [], {}
            for d in stmt.find_all(exp.ColumnDef):
                # a constraint is usually a ColumnConstraint wrapping a .kind;
                # some sqlglot nodes (InOutColumnConstraint…) sit in the list
                # directly and have no .kind — keep the node itself then
                kinds = [getattr(c, 'kind', c) for c in d.constraints]
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
                brut = rendre_sql(typ) if typ else ''
                # lowercase to match the PostgreSQL parser's output, but keep
                # string literals intact (ENUM('Active') must not become 'active')
                type_txt = brut if "'" in brut else brut.lower()
                cols.append(nouvelle_colonne(
                    d.name, type_txt,
                    any(isinstance(c, exp.NotNullColumnConstraint) for c in kinds),
                    rendre_sql(defc) if defc is not None else ''))
            for p in stmt.find_all(exp.PrimaryKey):
                noms = [c.name for c in p.expressions]
                if noms:
                    pk = noms
            comment = ''
            props = stmt.args.get('properties')
            for p in (props.expressions if props else []):
                if isinstance(p, exp.SchemaCommentProperty) and p.this is not None:
                    comment = p.this.name
            tables[k] = nouvelle_table(tbl.db or 'public', tbl.name, cols, pk,
                                       comment, colcomments)
            for fk in stmt.find_all(exp.ForeignKey):
                ref = fk.args.get('reference')
                if ref:
                    ajouter_fk(k, [c.name for c in fk.expressions], ref, nom_fk(fk))
            # inline UNIQUE constraints become indexes
            for u in stmt.find_all(exp.UniqueColumnConstraint):
                sch = u.this if u.this is not None else None
                noms = [e.name for e in getattr(sch, 'expressions', [])] if sch else []
                if noms:
                    tables[k]['index'].append({'nom': '', 'cols': noms, 'unique': True})
        elif isinstance(stmt, exp.Create) and stmt.kind == 'INDEX':
            idx = stmt.this
            tbl = idx.args.get('table') if idx is not None else None
            if tbl is not None:
                k = cle(tbl)
                if k in tables:
                    tables[k]['index'].append(
                        {'nom': idx.name, 'unique': bool(stmt.args.get('unique')),
                         'cols': [c.name for c in idx.find_all(exp.Column)]})
        elif isinstance(stmt, exp.Alter):
            src_tbl = stmt.find(exp.Table)
            if src_tbl:
                k = cle(src_tbl)
                for fk in stmt.find_all(exp.ForeignKey):
                    ref = fk.args.get('reference')
                    if ref:
                        ajouter_fk(k, [c.name for c in fk.expressions], ref, nom_fk(fk))
                for u in stmt.find_all(exp.UniqueColumnConstraint):
                    if k not in tables:
                        continue
                    cont = u.find_ancestor(exp.Constraint)
                    sch = u.this if u.this is not None else None
                    noms = [e.name for e in getattr(sch, 'expressions', [])] if sch else []
                    if noms:
                        tables[k]['index'].append(
                            {'nom': cont.name if cont else '', 'cols': noms, 'unique': True})

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


# --- hardening the untrusted-upload surface (converters + model XML) ---
# A hosted service parses files it did not write, so these paths must not let a
# crafted input hang the process or exhaust memory.
DELAI_OUTIL = 300          # kill an external converter after this many seconds
LIMITE_XML = 80 * 1024 * 1024   # cap the model XML we decompress/parse (80 MB)


def executer(cmd, **kw):
    """subprocess.run with a mandatory timeout, so a converter that hangs on a
    forged input cannot block the process forever."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=DELAI_OUTIL, **kw)
    except subprocess.TimeoutExpired:
        sys.exit(f'{cmd[0]} timed out after {DELAI_OUTIL}s')


def parser_xml(donnees):
    """Parse model XML, rejecting a DTD/entity declaration up front. A model
    file never legitimately carries one, and it is the vector for the
    entity-expansion ("billion laughs") and external-entity (XXE) attacks that
    Python's stdlib XML parser does not defend against on its own."""
    # scan the whole buffer, not just the head: a large leading comment could
    # otherwise push the DOCTYPE past a fixed window
    if b'<!DOCTYPE' in donnees or b'<!ENTITY' in donnees:
        sys.exit('refusing an XML document that declares a DTD or entities')
    try:
        return ET.fromstring(donnees)
    except ET.ParseError as e:
        sys.exit(f'malformed model XML: {e}')


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
        return executer(['pgmodeler-cli', '--export-to-file', '--input',
                         entree, '--output', str(sortie), '--silent'])

    r = exporter(chemin)
    if r.returncode or not sortie.exists():
        # a .dbm from an older pgModeler often loads only after --fix-model
        repare = coin / 'repare.dbm'
        executer(['pgmodeler-cli', '--fix-model', '--input', chemin,
                  '--output', str(repare), '--silent'])
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
    r = executer([a.format(entree=chemin, sortie=str(sortie)) for a in cmd], env=env)
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
    env = dict(os.environ, DATABASE_URL='postgresql://u:p@localhost:5432/d')
    return sql_depuis_convertisseur(
        chemin, 'prisma',
        ['prisma', 'migrate', 'diff', '--from-empty', '--to-schema-datamodel',
         '{entree}', '--script'], 'Prisma', vers_stdout=True, env=env)


def sql_depuis_db(url):
    """Dump a live database's schema to SQL (CLI only). SECURITY: never expose
    this on a public service — it makes the process connect to any database the
    caller names, including internal ones (SSRF). Returns (sql_path, dialect)."""
    env = dict(os.environ)
    if url.startswith(('postgres://', 'postgresql://')):
        outil = 'pg_dump'
        cmd = ['pg_dump', '-s', '--no-owner', '--no-privileges', url]
        dialecte = 'postgres'
    elif url.startswith(('mysql://', 'mariadb://')):
        from urllib.parse import urlparse, unquote
        u = urlparse(url)
        outil = 'mysqldump'
        cmd = ['mysqldump', '--no-data', '--skip-comments', '--column-statistics=0',
               '-h', u.hostname or 'localhost', '-P', str(u.port or 3306),
               '-u', unquote(u.username or 'root'), u.path.lstrip('/')]
        if u.password:
            env['MYSQL_PWD'] = unquote(u.password)  # avoids the password on argv
        dialecte = 'mysql'
    else:
        sys.exit('--db expects a postgresql:// or mysql:// URL')
    if not shutil.which(outil):
        sys.exit(f'--db needs {outil} in PATH')
    r = executer(cmd, env=env)
    if r.returncode or not r.stdout.strip():
        sys.exit(f'{outil} failed:\n{r.stderr.strip()}')
    sortie = Path(tempfile.mkdtemp(prefix='mcdview-')) / 'db.sql'
    sortie.write_text(r.stdout)
    return str(sortie), dialecte


def analyser_mwb(chemin):
    """Parse a MySQL Workbench .mwb model natively (zip + GRT XML, stdlib only).

    The .mwb is a zip whose document.mwb.xml is a GRT object tree: schemas hold
    tables, tables hold columns/indices/foreign keys, and cross-references
    (a column's type, a PK's columns, an FK's endpoints) are id links resolved
    against every object's `id` attribute.
    """
    try:
        z = zipfile.ZipFile(chemin)
    except zipfile.BadZipFile:
        sys.exit('not a MySQL Workbench file (.mwb must be a zip archive)')
    with z:
        try:
            info = z.getinfo('document.mwb.xml')
        except KeyError:
            sys.exit('not a MySQL Workbench file (no document.mwb.xml inside)')
        # read through a stream and stop at the cap: a tiny .mwb can otherwise
        # decompress into gigabytes (zip bomb)
        with z.open(info) as f:
            donnees = f.read(LIMITE_XML + 1)
    if len(donnees) > LIMITE_XML:
        sys.exit('the .mwb model XML is too large (possible zip bomb)')
    racine = parser_xml(donnees)

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
                cols.append(nouvelle_colonne(cn, type_colonne(c),
                            txt(c, 'isNotNull') == '1', txt(c, 'defaultValue')))
            pk = []
            for idx in objets(t, 'indices'):
                if txt(idx, 'isPrimary') == '1':
                    for ic in objets(idx, 'columns'):
                        rc = txt(ic, 'referencedColumn')
                        if rc in col_par_id:
                            pk.append(col_par_id[rc][0])
            tables[cle] = nouvelle_table(schema, nom, cols, pk, txt(t, 'comment'))

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
                fks.append(nouvelle_fk(de, scol, vers, dcol, nom))
    return tables, fks


IRREGULIERS = {'people': 'person', 'children': 'child', 'men': 'man',
               'women': 'woman', 'teeth': 'tooth', 'feet': 'foot',
               'mice': 'mouse', 'geese': 'goose', 'media': 'medium',
               'data': 'datum', 'people_id': 'person'}


def singulariser(mot):
    """Rough ActiveRecord singularize, for the default FK column name."""
    if mot.lower() in IRREGULIERS:
        return IRREGULIERS[mot.lower()]
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
    # opener + string-search for the block's `end` (not a lazy `.*?` spanning to
    # `end`, which backtracks on many unterminated create_table openers)
    RE_CT = re.compile(r'create_table\s+["\']([^"\']+)["\']\s*(,[^\n]*)?\s+do\s*\|(\w+)\|')
    RE_FIN = re.compile(r'\n[ \t]*end\b')
    for m in RE_CT.finditer(src):
        f = RE_FIN.search(src, m.end())
        if not f:
            continue
        nom, opts, var = m.group(1), m.group(2) or '', m.group(3)
        corps = src[m.end():f.start()]
        cle = f'public.{nom}'
        cols, pk = [], []
        if 'id: false' not in opts:
            mpk = re.search(r'primary_key:\s*["\']([^"\']+)["\']', opts)
            pkn = mpk.group(1) if mpk else 'id'
            mid = re.search(r'\bid:\s*:(\w+)', opts)
            cols.append(nouvelle_colonne(pkn, mid.group(1) if mid else 'bigint', True))
            pk = [pkn]
        for cm in re.finditer(r'\b' + re.escape(var) + r'\.(\w+)\s+["\'"]([^"\'"]+)["\'"]([^\n]*)', corps):
            typ, cn, reste = cm.groups()
            if typ == 'index':
                continue
            defc = re.search(r'default:\s*("[^"]*"|\'[^\']*\'|[^,\n]+)', reste)
            defaut = defc.group(1).strip('\'"') if defc else ''
            if typ in ('references', 'belongs_to'):
                cols.append(nouvelle_colonne(cn + '_id', 'bigint', 'null: false' in reste))
                if 'polymorphic: true' in reste:
                    cols.append(nouvelle_colonne(cn + '_type', 'string'))
            else:
                cols.append(nouvelle_colonne(cn, typ, 'null: false' in reste, defaut))
        tables[cle] = nouvelle_table('public', nom, cols, pk)
    for m in re.finditer(r'add_foreign_key\s+["\']([^"\']+)["\'],\s*["\']([^"\']+)["\']([^\n]*)', src):
        det, verst, reste = m.groups()
        mp = re.search(r'primary_key:\s*["\']([^"\']+)["\']', reste)
        de, vers = f'public.{det}', f'public.{verst}'
        if de not in tables or vers not in tables:
            continue
        mc = re.search(r'column:\s*["\']([^"\']+)["\']', reste)
        if mc:
            col = mc.group(1)
        else:
            # the default is <singular(to)>_id; singularization is heuristic
            # (statuses→status, people→person), so if the guess is not an
            # actual column, prefer a real <stem>_id column that matches
            col = singulariser(verst) + '_id'
            reels = {c['nom'] for c in tables[de]['cols']}
            if col not in reels:
                col = next((c for c in (singulariser(verst) + '_id', verst[:-2] + '_id',
                                        verst[:-1] + '_id', verst + '_id') if c in reels), col)
        fks.append(nouvelle_fk(de, col, vers, mp.group(1) if mp else 'id'))
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
    # %% starts a comment to end of line, anywhere; strip it before parsing so a
    # `%% note` line is not read as a `type name` attribute (bogus column)
    bloc = re.sub(r'%%.*', '', bloc)

    tables, fks = {}, []

    def table(nom):
        nom = nom.strip('"')
        cle = f'public.{nom}'
        if cle not in tables:
            tables[cle] = nouvelle_table('public', nom)
        return cle

    # entity blocks: NAME {\n attr* }. The opening brace must be followed by a
    # newline: a crow's-foot cardinality (o{, }o) also contains a brace but is
    # followed by the related entity's name on the same line, and must not be
    # mistaken for an entity block. The body runs to the next '}' found by
    # string search (not a lazy `.*?`, which backtracks catastrophically on many
    # openers with no closer). Blocks are stripped out to leave `masque` for the
    # relationship scan — both in one pass.
    # identifier runs are length-bounded so finditer cannot backtrack O(n²) on
    # a long non-matching run (a crafted .mmd/.md is untrusted input)
    RE_OUVRE = re.compile(r'(?:"([^"]{1,255})"|([A-Za-z_][\w-]{0,127}))[ \t]*\{[ \t]*\r?\n')
    reste_masque, pos = [], 0
    for m in RE_OUVRE.finditer(bloc):
        if m.start() < pos:               # opener inside a block already consumed
            continue
        ferme = bloc.find('}', m.end())
        if ferme == -1:                   # unterminated block: not a real entity
            continue
        reste_masque.append(bloc[pos:m.start()])
        pos = ferme + 1
        cle = table(m.group(1) or m.group(2))
        for ligne in bloc[m.end():ferme].splitlines():
            if re.match(r'\s*direction\s+\w+\s*$', ligne):  # layout directive
                continue
            # type name [PK[, FK…]] ["free-text comment"] — keys may be
            # comma-separated, the trailing quoted comment is optional
            am = re.match(r'\s*(\S+)\s+(\S+)((?:[\s,]+(?:PK|FK|UK))*)'
                          r'\s*(?:"([^"]*)")?', ligne)
            if not am:
                continue
            typ, cn, cles, commentaire = am.groups()
            tables[cle]['cols'].append(nouvelle_colonne(cn, typ))
            if 'PK' in cles:
                tables[cle]['pk'].append(cn)
            if commentaire:
                tables[cle]['colcomments'][cn] = commentaire
    reste_masque.append(bloc[pos:])

    # relationships: A <card>--|..<card> B : label. One per line in Mermaid, so
    # scan line by line and skip any line without a connector — a long crafted
    # line then costs nothing instead of backtracking the identifier run.
    RE_REL = re.compile(
        r'(?:"([^"]{1,255})"|([A-Za-z_][\w-]{0,127}))\s+([|}o]{1,2})(?:--|\.\.)([|{o]{1,2})\s+'
        r'(?:"([^"]{1,255})"|([A-Za-z_][\w-]{0,127}))')
    masque = ''.join(reste_masque)
    for ligne in masque.splitlines():
        # a real relationship line is short; skip an abnormally long one so the
        # regex cannot be made to scan many start positions on crafted input
        if len(ligne) > 2000 or ('--' not in ligne and '..' not in ligne):
            continue
        m = RE_REL.search(ligne)
        if not m:
            continue
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
        fks.append(nouvelle_fk(de, '', vers, cible))
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
                out.append(cur)
                cur = ''
            else:
                cur += ch
        if cur.strip():
            out.append(cur)
        return out

    # a multi-project schema defines its own table function via a creator:
    # `const createTable = pgTableCreator(...)`; treat those variables as table
    # constructors alongside the built-in pg/mysql/sqliteTable
    fabriques = ['pgTable', 'mysqlTable', 'sqliteTable']
    fabriques += re.findall(
        r'(?:const|let|var)\s+(\w+)\s*=\s*(?:pg|mysql|sqlite)TableCreator\s*\(', src)
    motif_table = '|'.join(re.escape(f) for f in dict.fromkeys(fabriques))
    for m in re.finditer(
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:' + motif_table + r')\s*\(\s*'
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
            cols.append(nouvelle_colonne(col, typ, '.notNull(' in entree))
            if '.primaryKey(' in entree:
                pk.append(col)
            rm = re.search(r'\.references\(\s*\(\s*\)\s*=>\s*(\w+)\.(\w+)', entree)
            if rm:
                refs.append((cle, col, rm.group(1), rm.group(2)))
        tables[cle] = nouvelle_table('public', nom, cols, pk)

    for de, col, tvar, tfield in refs:
        vers = var_table.get(tvar)
        if de in tables and vers in tables:
            fks.append(nouvelle_fk(de, col, vers, var_cols.get(tvar, {}).get(tfield, '')))
    return tables, fks


def positions_dbm(chemin, tables):
    donnees = Path(chemin).read_bytes()[:LIMITE_XML + 1]
    if len(donnees) > LIMITE_XML:
        sys.exit('the .dbm model is too large to read positions from')
    root = parser_xml(donnees)
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
        # column height aimed at a roughly square zone (√area), so a schema
        # neither stretches into an unreadable 40:1 band nor stacks a handful
        # of small tables into a tall single column. A low floor keeps a
        # 2-3 table schema compact instead of over-splitting it.
        haut_totale = sum(h + GAP_Y for w, h in dims.values())
        larg_moy = sum(w + GAP_X for w, h in dims.values()) / len(dims)
        cible_h = max(650, (haut_totale * larg_moy) ** 0.5)
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
        'placeholder="chercher table ou colonne…"': 'placeholder="find a table or column…"',
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
        '<h4>Index</h4>': '<h4>Indexes</h4>',
        'aucune table': 'no table',
        '"cadrer ce schéma"': '"frame this schema"',
        '"add">ajoutée<': '"add">added<',
        '"mod">modifiée<': '"mod">changed<',
        '"del">supprimée<': '"del">removed<',
        'const MOT = "touchées";': 'const MOT = "touched";',
        'renommée depuis <b>': 'renamed from <b>',
        # graph-analysis toolbar buttons and their tooltips
        'title="teinter les tables par nombre de relations"':
            'title="shade tables by number of relations"',
        'title="surligner les cycles de clés étrangères"':
            'title="highlight foreign-key cycles"',
        'title="chemin de jointure entre deux tables">⇢ jointure':
            'title="join path between two tables">⇢ join path',
        # graph-analysis runtime strings (TXT + impact buttons)
        '"Aucune table liée."': '"No related table."',
        '"Aucun cycle de clé étrangère."': '"No foreign-key cycle."',
        '"Chemin de jointure : cliquez la première table."':
            '"Join path: click the first table."',
        '"Cliquez la seconde table (Échap pour annuler)."':
            '"Click the second table (Esc to cancel)."',
        '"Chemin de jointure"': '"Join path"',
        '"Pas de chemin de jointure entre ces deux tables."':
            '"No join path between these two tables."',
        '"sauts"': '"hops"',
        '"Copier le SQL"': '"Copy the SQL"',
        '"Copié"': '"Copied"',
        '"▲ dépend de"': '"▲ depends on"',
        '"▼ dont dépendent"': '"▼ depended on by"',
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
    # browsers strip tab/CR/LF and trim control chars before resolving a URL,
    # which can re-form a "java\tscript:" scheme past a naive check; remove them
    # first so the scheme test sees the real scheme
    u = re.sub(r'[\x00-\x20\x7f]', '', u)
    schema = re.match(r'([a-z][a-z0-9+.-]*):', u, re.I)
    if schema and schema.group(1).lower() not in ('http', 'https', 'mailto'):
        return '#'
    return u


MIMES_LOGO = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.webp': 'image/webp',
              '.ico': 'image/x-icon'}


def composer_page(tables, fks, titre, lang='fr', couleurs=None, dialecte='postgresql',
                  home_url=None, logo_file=None, credit=None, credit_url=None,
                  mode_diff=False):
    """Assemble the final HTML page from parsed and positioned tables."""
    couleurs = dict(couleurs or {})
    for i, s in enumerate(sorted({t['schema'] for t in tables.values()})):
        couleurs.setdefault(s, PALETTE[i % len(PALETTE)])
    donnees = {'schemas': couleurs, 'tables': list(tables.values()), 'fks': fks,
               'dialecte': dialecte, 'diff': mode_diff}
    # '<' escaped in the JSON: no '</script>' or '<!--' can leak from the data
    json_txt = json.dumps(donnees, ensure_ascii=False).replace('<', '\\u003c')
    html = traduire(ressource('templates/explorateur.html').read_text(), lang)
    logo = ressource('logo.svg').read_text()
    html = html.replace('__DONNEES__', json_txt).replace('__TITRE__', echapper(titre))
    html = html.replace('__VERSION__', echapper('mcdview ' + version_mcdview()))
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
        b64 = base64.b64encode(ressource('logo.svg').read_bytes()).decode()
        contenu = (f'<img src="data:image/svg+xml;base64,{b64}" width="18" '
                   f'height="18" alt=""><b>{echapper(credit)}</b>')
        badge = (f'<a href="{echapper(url_sure(credit_url))}" target="_blank" '
                 f'rel="noopener">{contenu}</a>' if credit_url
                 else f'<span>{contenu}</span>')
    return html.replace('__CREDIT__', badge)


def charger(source, dialect='auto'):
    """Parse any supported model file into (tables, fks, dialect). Converter
    formats (.dbm/.dbml/.prisma) are turned into SQL first; the others are
    native. One dispatch, reused by the main input and the --diff baseline."""
    if source.endswith('.dbm'):
        tables, fks, _ = analyser(sql_depuis_dbm(source), 'postgres')
        return tables, fks, 'postgres'
    if source.endswith('.dbml'):
        tables, fks, _ = analyser(sql_depuis_dbml(source), 'postgres')
        return tables, fks, 'postgres'
    if source.endswith('.prisma'):
        return analyser(sql_depuis_prisma(source), 'auto')
    if source.endswith('.mwb'):
        return (*normaliser_casse(*analyser_mwb(source)), 'mysql')
    if source.endswith('.rb'):
        return (*normaliser_casse(*analyser_schema_rb(source)), 'rails')
    if source.endswith(('.mmd', '.mermaid', '.md')):
        return (*normaliser_casse(*analyser_mermaid(source)), 'mermaid')
    if source.endswith('.ts'):
        return (*normaliser_casse(*analyser_drizzle(source)), 'drizzle')
    return analyser(source, dialect)


def comparer(vieux, neuf):
    """Merge an old and a new (tables, fks) into a single model where every
    table, column and FK carries a `diff` status: 'ajoute' (in the new only),
    'supprime' (in the old only), 'modifie' (changed), or none (identical). The
    new definition wins for a changed item; removed items are kept so the page
    can show them struck through. A table present only in the old and one
    present only in the new with the same set of column names are matched as a
    rename (the new one gets `renomme_de`), not a remove+add pair."""
    vt, vf = vieux
    nt, nf = neuf

    # rename detection: pair an old-only table with a new-only table by column
    # overlap. An exact set match wins first; then the best Jaccard overlap
    # above a threshold, so a table renamed AND edited is still caught. Each
    # side is used at most once, best pairs first.
    def signature(t):
        return frozenset(c['nom'] for c in t['cols'])
    news = [c for c in nt if c not in vt]
    olds = [c for c in vt if c not in nt]
    renomme = {}                       # new_key -> old_key
    paires = []                        # (score, new_key, old_key)
    for nk in news:
        sn = signature(nt[nk])
        if len(sn) < 2:
            continue
        for ok in olds:
            so = signature(vt[ok])
            if len(so) < 2:
                continue
            inter = len(sn & so)
            if not inter:
                continue
            jac = inter / len(sn | so)
            # 1.0 (exact) or a strong overlap with ≥2 shared columns
            if jac == 1.0 or (jac >= 0.6 and inter >= 2):
                paires.append((jac, nk, ok))
    pris_new, pris_old = set(), set()
    for jac, nk, ok in sorted(paires, key=lambda p: -p[0]):
        if nk not in pris_new and ok not in pris_old:
            renomme[nk] = ok
            pris_new.add(nk)
            pris_old.add(ok)
    old_renomme = set(renomme.values())

    tables = {}
    for cle in list(nt) + [c for c in vt if c not in nt and c not in old_renomme]:
        nou = nt.get(cle)
        anc = vt.get(cle) or (vt.get(renomme[cle]) if cle in renomme else None)
        base = nou or anc
        t = nouvelle_table(base['schema'], base['nom'], pk=list(base['pk']),
                           comment=base['comment'], colcomments=dict(base['colcomments']))
        if cle in renomme:
            t['diff'] = 'modifie'
            t['renomme_de'] = vt[renomme[cle]]['nom']
        elif nou and not anc:
            t['diff'] = 'ajoute'
        elif anc and not nou:
            t['diff'] = 'supprime'
        acols = {c['nom']: c for c in (anc['cols'] if anc else [])}
        ncols = {c['nom']: c for c in (nou['cols'] if nou else [])}
        change = False
        for nom in list(ncols) + [n for n in acols if n not in ncols]:
            oc, ncc = acols.get(nom), ncols.get(nom)
            col = dict(ncc or oc)
            if ncc and not oc:
                col['diff'] = 'ajoute'
            elif oc and not ncc:
                col['diff'] = 'supprime'
            elif oc != ncc:
                col['diff'] = 'modifie'
                if oc['type'] != ncc['type']:
                    col['avant'] = oc['type']  # previous type: "numeric → bigint"
            change = change or 'diff' in col
            t['cols'].append(col)
        # indexes/unique constraints, matched by name
        aidx = {i['nom']: i for i in (anc['index'] if anc else [])}
        nidx = {i['nom']: i for i in (nou['index'] if nou else [])}
        for nom in list(nidx) + [n for n in aidx if n not in nidx]:
            oi, ni = aidx.get(nom), nidx.get(nom)
            ix = dict(ni or oi)
            if ni and not oi:
                ix['diff'] = 'ajoute'
            elif oi and not ni:
                ix['diff'] = 'supprime'
            elif oi != ni:
                ix['diff'] = 'modifie'
            change = change or 'diff' in ix
            t['index'].append(ix)
        if 'diff' not in t and change:
            t['diff'] = 'modifie'
        tables[cle] = t

    # FK endpoints on a renamed table are translated to the new key so a FK
    # untouched apart from the rename does not show up as removed + added
    inv = {ok: nk for nk, ok in renomme.items()}
    def cle_fk(f, traduit=False):
        de = inv.get(f['de'], f['de']) if traduit else f['de']
        vers = inv.get(f['vers'], f['vers']) if traduit else f['vers']
        return (de, f['col'], vers, f['colcible'])
    anciens = {cle_fk(f, True): f for f in vf}
    nouveaux = {cle_fk(f): f for f in nf}
    fks = []
    for k in list(nouveaux) + [x for x in anciens if x not in nouveaux]:
        f = dict(nouveaux.get(k) or anciens[k])
        if k in nouveaux and k not in anciens:
            f['diff'] = 'ajoute'
        elif k in anciens and k not in nouveaux:
            f['diff'] = 'supprime'
        # point a surviving old FK at the renamed table's new endpoints
        f['de'], f['col'], f['vers'], f['colcible'] = k
        fks.append(f)
    return tables, fks


def resume_diff(tables, fks, baseline=None):
    """A machine-readable summary of a comparer() result, for a caller (like a
    hosting service) that wants change counts and a change list without parsing
    the HTML. English status names: added / removed / changed."""
    trad = {'ajoute': 'added', 'supprime': 'removed', 'modifie': 'changed'}
    ct = {'added': 0, 'removed': 0, 'changed': 0, 'unchanged': 0}
    cc = {'added': 0, 'removed': 0, 'changed': 0}
    cf = {'added': 0, 'removed': 0}
    ci = {'added': 0, 'removed': 0, 'changed': 0}
    liste_tables = []
    for t in tables.values():
        st = trad.get(t.get('diff'), 'unchanged')
        ct[st] += 1
        entree = {'table': f"{t['schema']}.{t['nom']}", 'status': st}
        if t.get('renomme_de'):
            entree['renamed_from'] = t['renomme_de']
        if st == 'changed':  # column-level detail only where the table persists
            cols = []
            for c in t['cols']:
                if not c.get('diff'):
                    continue
                s = trad[c['diff']]
                cc[s] += 1
                d = {'name': c['nom'], 'status': s, 'type': c['type']}
                if 'avant' in c:
                    d['was'] = c['avant']
                cols.append(d)
            entree['columns'] = cols
            idx = [{'name': i['nom'], 'columns': i['cols'], 'unique': i['unique'],
                    'status': trad[i['diff']]}
                   for i in t['index'] if i.get('diff')]
            for i in idx:
                ci[i['status']] += 1
            if idx:
                entree['indexes'] = idx
        if st != 'unchanged':
            liste_tables.append(entree)
    liste_fks = []
    for f in fks:
        if not f.get('diff'):
            continue
        s = trad[f['diff']]
        cf[s] += 1
        liste_fks.append({'from': f['de'], 'column': f['col'], 'to': f['vers'],
                          'to_column': f['colcible'], 'status': s})
    return {'diff': True, 'baseline': baseline,
            'counts': {'tables': ct, 'columns': cc, 'foreign_keys': cf, 'indexes': ci},
            'tables': liste_tables, 'foreign_keys': liste_fks}


def vers_mermaid(tables, fks):
    """Render the model as a Mermaid erDiagram. Pasted in a Markdown file, it
    is rendered natively by GitHub and GitLab — a static diagram (not the
    interactive page). Names and types are sanitised to Mermaid's identifier
    grammar; the interactive page stays the way to explore a big model."""
    # a unique, Mermaid-safe entity name per table (prefix the schema on a
    # cross-schema name clash)
    homonymes = defaultdict(list)
    for cle, t in tables.items():
        homonymes[t['nom']].append(cle)
    noms = {}
    for cle, t in tables.items():
        base = t['nom'] if len(homonymes[t['nom']]) == 1 else f"{t['schema']}_{t['nom']}"
        noms[cle] = re.sub(r'\W', '_', base) or 'table'

    def type_court(s):
        m = re.match(r'\w+', s or '')  # Mermaid wants a single-token type
        return m.group(0) if m else 'text'

    fkcols = defaultdict(set)
    for f in fks:
        fkcols[f['de']].add(f['col'])

    lignes = ['erDiagram']
    for cle, t in tables.items():
        lignes.append(f'    {noms[cle]} {{')
        for c in t['cols']:
            marques = (['PK'] if c['nom'] in t['pk'] else []) + \
                      (['FK'] if c['nom'] in fkcols[cle] else [])
            suffixe = ' ' + ', '.join(marques) if marques else ''
            # a backslash inside an f-string expression is a syntax error before
            # Python 3.12, so build the sanitized name outside the f-string
            nom_col = re.sub(r'\W', '_', c['nom'])
            lignes.append(f'        {type_court(c["type"])} {nom_col}{suffixe}')
        lignes.append('    }')
    vues = set()
    for f in fks:
        if f['de'] not in noms or f['vers'] not in noms:
            continue
        paire = (f['vers'], f['de'])
        if paire in vues:
            continue
        vues.add(paire)
        lignes.append(f'    {noms[f["vers"]]} ||--o{{ {noms[f["de"]]} : ""')
    return '\n'.join(lignes) + '\n'


def principal():
    ap = argparse.ArgumentParser(description="interactive HTML explorer for a PostgreSQL data model")
    ap.add_argument('--version', action='version', version=f'mcdview {version_mcdview()}')
    ap.add_argument('sql', nargs='*', metavar='sql|dbm|dbml|mwb|rb|mmd|ts',
                    help='one or more model files (merged into one model); '
                         'omit with --db')
    ap.add_argument('--db', metavar='URL',
                    help='dump a live database schema instead (postgresql://… or '
                         'mysql://…). CLI ONLY — never expose on a public service (SSRF)')
    ap.add_argument('--diff', metavar='BASELINE',
                    help='compare against an older model (any supported format): '
                         'tables/columns/FKs added, removed or changed are colored')
    ap.add_argument('--summary', metavar='FILE',
                    help='with --diff: also write a JSON summary of the changes to FILE')
    ap.add_argument('--diagnose', action='store_true',
                    help='print a JSON diagnosis of the input (status, dialect, '
                         'counts, anomalies) instead of a page; never fails')
    ap.add_argument('--to-mermaid', action='store_true',
                    help='output a Mermaid erDiagram (paste in a .md; GitHub/GitLab '
                         'render it) instead of the HTML page; to -o if given, else stdout')
    ap.add_argument('--watch', action='store_true',
                    help='regenerate the page whenever the input file changes '
                         '(Ctrl-C to stop); file input only')
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
    if args.summary and not args.diff:
        ap.error('--summary only applies with --diff')

    if args.diagnose:
        diagnostiquer(args, ap)
        return

    generer(args, ap)
    if args.watch:
        if args.db or args.to_mermaid or not args.sql:
            ap.error('--watch needs a model file (not --db or --to-mermaid)')
        surveiller(args, ap)


def diagnostiquer(args, ap):
    """Print a JSON diagnosis of the input and exit 0, whatever happens — a
    hosting service calls this alongside generation to decide whether an upload
    is worth reporting (crash / no table / content anomaly), without parsing the
    HTML. One file input (the per-upload case); --db/--diff are not diagnosed."""
    if not args.sql:
        ap.error('--diagnose needs a model file')
    source = args.sql[0]
    diag = {'status': 'ok', 'file': Path(source).name, 'format': Path(source).suffix.lstrip('.') or 'sql',
            'dialect': None, 'tables': 0, 'fks': 0,
            'anomalies': {'empty_tables': 0, 'phantom_columns': 0,
                          'fks_without_target': 0, 'disconnected_tables': 0},
            'error': None, 'mcdview_version': version_mcdview()}
    try:
        tables, fks, dialecte = charger(source, args.dialect)
        diag['dialect'] = dialecte
        if not tables:
            diag['status'] = 'no_table'
        else:
            diag['tables'], diag['fks'] = len(tables), len(fks)
            a = diag['anomalies']
            a['empty_tables'] = sum(1 for t in tables.values() if not t['cols'])
            a['fks_without_target'] = sum(1 for f in fks if not f['colcible'])
            for t in tables.values():
                noms = {c['nom'] for c in t['cols']}
                a['phantom_columns'] += sum(1 for p in t['pk'] if p not in noms)
            for f in fks:
                src = tables.get(f['de'])
                if src and f['col'] and f['col'] not in {c['nom'] for c in src['cols']}:
                    a['phantom_columns'] += 1
            # several tables and not one FK is almost always a parser gap (inline
            # REFERENCES missed, an unsupported dialect…), rarely a real model —
            # a soft flag so the hosting side can surface and sample these
            if diag['tables'] >= 2 and diag['fks'] == 0:
                a['disconnected_tables'] = diag['tables']
            if any(a.values()):
                diag['status'] = 'anomaly'
    except SystemExit as e:          # charger()/converters call sys.exit on failure
        diag['status'] = 'error'
        diag['error'] = str(e)[:500]
    except Exception as e:
        diag['status'] = 'error'
        diag['error'] = f'{type(e).__name__}: {e}'[:500]
    print(json.dumps(diag, ensure_ascii=False, indent=2))


def surveiller(args, ap):
    """Regenerate on every change to the input file(s). Polls mtimes — no
    dependency — and swallows a transient parse error so a mid-edit save does
    not stop the loop."""
    import time
    fichiers = list(args.sql) + [f for f in (args.diff, args.dbm) if f]
    print(f'watching {", ".join(fichiers)} (Ctrl-C to stop)…')
    empreinte = {f: os.path.getmtime(f) for f in fichiers if os.path.exists(f)}
    try:
        while True:
            time.sleep(0.5)
            actuel = {f: os.path.getmtime(f) for f in fichiers if os.path.exists(f)}
            if actuel != empreinte:
                empreinte = actuel
                try:
                    generer(args, ap)
                except SystemExit as e:  # a bad mid-edit save: report, keep going
                    print(f'  (skipped: {e})')
    except KeyboardInterrupt:
        print('\nstopped.')


def generer(args, ap):
    if args.db:
        source, dialecte = sql_depuis_db(args.db)
        tables, fks, dialecte = analyser(source, dialecte)
        nom_defaut = re.sub(r'\W+', '_', args.db.rstrip('/').rsplit('/', 1)[-1].split('?')[0]) or 'database'
        sortie_defaut = nom_defaut + '.html'
    else:
        if not args.sql:
            ap.error('provide a model file, or --db URL to read a live database')
        source = args.sql[0]
        nom_defaut = Path(source).stem
        sortie_defaut = str(Path(source).with_suffix('.html'))
        # a single .dbm carries its own table positions: reuse them
        if len(args.sql) == 1 and source.endswith('.dbm') and not args.dbm:
            args.dbm = source
        # several files are merged into one model (a schema split across files).
        # Plain SQL/dialect files are concatenated and parsed together, so a FK
        # pointing from one file to a table in another still resolves; special
        # formats (.dbm/.dbml/…) are parsed each and merged (a cross-file FK to
        # a different file may not resolve).
        speciales = ('.dbm', '.dbml', '.prisma', '.mwb', '.rb',
                     '.mmd', '.mermaid', '.md', '.ts')
        if len(args.sql) == 1:
            tables, fks, dialecte = charger(source, args.dialect)
        elif all(not f.endswith(speciales) for f in args.sql):
            combine = '\n\n'.join(open(f, errors='replace').read() for f in args.sql)
            tmp = Path(tempfile.mkdtemp(prefix='mcdview-')) / 'merged.sql'
            tmp.write_text(combine)
            tables, fks, dialecte = analyser(str(tmp), args.dialect)
        else:
            tables, fks, dialecte = {}, [], 'auto'
            vus = set()
            for f in args.sql:
                tt, ff, dd = charger(f, args.dialect)
                tables.update(tt)
                for lien in ff:
                    cle = (lien['de'], lien['col'], lien['vers'], lien['colcible'])
                    if cle not in vus:
                        vus.add(cle)
                        fks.append(lien)
                if dd != 'auto':
                    dialecte = dd
    if not tables:
        sys.exit('no table found: the DDL must contain CREATE TABLE statements'
                 + indice_dialecte(source))

    if args.to_mermaid:
        mmd = vers_mermaid(tables, fks)
        if args.sortie:
            Path(args.sortie).write_text(mmd)
            print(f'{len(tables)} tables, {len(fks)} FKs → {args.sortie} (Mermaid)')
        else:
            sys.stdout.write(mmd)
        return

    if args.diff:
        vieux = charger(args.diff, args.dialect)[:2]
        tables, fks = comparer(vieux, (tables, fks))
        args.dbm = None  # the merged model has removed tables: auto-layout it

    couleurs = {}
    if args.dbm:
        couleurs = positions_dbm(args.dbm, tables)
    if not args.dbm or all(t['x'] == 0 and t['y'] == 0 for t in tables.values()):
        placement_auto(tables, fks)

    if args.fk_audit:
        motif = re.compile(args.fk_audit)
        for f in fks:
            f['audit'] = bool(motif.search(f['nom']))

    titre = args.titre or nom_defaut
    sortie = args.sortie or sortie_defaut
    Path(sortie).write_text(composer_page(tables, fks, titre, args.lang, couleurs,
                                          dialecte, args.home_url, args.logo,
                                          args.credit, args.credit_url, bool(args.diff)))
    if args.diff:
        if args.summary:
            resume = resume_diff(tables, fks, args.diff)
            Path(args.summary).write_text(json.dumps(resume, ensure_ascii=False, indent=2))
        nt = [t for t in tables.values() if t.get('diff')]
        cpt = {s: sum(t.get('diff') == s for t in tables.values())
               for s in ('ajoute', 'supprime', 'modifie')}
        print(f'diff vs {args.diff}: {cpt["ajoute"]} tables added, '
              f'{cpt["supprime"]} removed, {cpt["modifie"]} changed'
              f' ({len(nt)} of {len(tables)} touched) → {sortie}')
    else:
        naudit = sum(1 for f in fks if f['audit'])
        print(f'{len(tables)} tables, {len(fks)} FKs'
              + (f' (including {naudit} audit FKs)' if naudit else '') + f' → {sortie}')


if __name__ == '__main__':
    principal()
