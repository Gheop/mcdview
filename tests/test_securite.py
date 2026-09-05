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
    # caller-supplied credit / logo-link: text escaped, URL schemes neutralized
    page = mcdview.composer_page(
        tables, fks, 'x', 'en',
        home_url='javascript:alert(1)', credit='<b>x</b>',
        credit_url='javascript:alert(2)')
    if re.search(r'href="\s*(javascript|data|vbscript):', page, re.I):
        echecs.append('credit/home_url: schéma d\'URL dangereux dans un href')
    if '<b>x</b>' in page:
        echecs.append('credit: texte non échappé')
    # URL schemes obfuscated with tab/newline/control chars (browsers strip
    # them and re-form the scheme) must be neutralized to '#'
    for u in ['java\tscript:alert(1)', 'java\nscript:alert(1)',
              '\x01javascript:alert(1)', 'jav\rascript:alert(1)', 'DATA:text/html,x']:
        if mcdview.url_sure(u) != '#':
            echecs.append(f'url_sure: schéma obfusqué non neutralisé: {u!r}')
    # a hostile schema fill-color (from a .dbm) must be escaped in the island —
    # it is injected into innerHTML at runtime, so no raw < may reach it
    couleur = mcdview.composer_page(
        tables, fks, 'x', 'en', couleurs={'public': "#000'><script>alert(9)</script>"})
    ilot = ilot_json(couleur)
    if '<' in ilot:
        echecs.append('couleur schéma: "<" brut dans le JSON injecté (XSS possible)')


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


def verifier_dos_natifs(echecs):
    """The native parsers reachable from an upload (.mmd/.md, .rb) must respect
    the same DoS budget — their block extraction used to backtrack on crafted
    input. Bombs are generated here, too big to commit."""
    cas = [
        ('mermaid openers', mcdview.analyser_mermaid, '.mmd',
         'erDiagram\n' + 'E {\n' * 200 + 'A' * 60000),
        ('mermaid ligne géante', mcdview.analyser_mermaid, '.mmd',
         'erDiagram\n' + 'A' * 200000 + ' ||--o{ B'),
        ('rails openers', mcdview.analyser_schema_rb, '.rb',
         'create_table "t" do |t|\n' * 3000 + 'A' * 60000),
    ]
    with tempfile.TemporaryDirectory() as td:
        for nom, fn, ext, contenu in cas:
            p = Path(td) / (re.sub(r'\W', '_', nom) + ext)
            p.write_text(contenu)
            t0 = time.perf_counter()
            try:
                fn(str(p))
            except Exception as e:
                echecs.append(f'{nom}: exception {e!r}')
                continue
            ms = (time.perf_counter() - t0) * 1000
            print(f'  {"OK " if ms < BUDGET_MS else "LENT"} {nom:24s} '
                  f'{p.stat().st_size // 1024:5d} KiB {ms:7.0f} ms')
            if ms >= BUDGET_MS:
                echecs.append(f'{nom}: {ms:.0f} ms > budget {BUDGET_MS} ms (DoS)')


def verifier_uploads(echecs):
    """The untrusted-upload surface: model XML and external converters must not
    let a crafted file expand without bound or hang the process."""
    import io
    import zipfile

    # 1. entity-expansion ("billion laughs") / XXE: a DTD or entity block in
    #    model XML is refused outright
    bombe = (b'<?xml version="1.0"?>\n<!DOCTYPE lolz [<!ENTITY a "aa">\n'
             b'<!ENTITY b "&a;&a;">]>\n<data>&b;</data>')
    try:
        mcdview.parser_xml(bombe)
        echecs.append('parser_xml: DTD/entités acceptées (bombe d\'entités possible)')
    except SystemExit:
        pass

    # 2. zip bomb: the decompressed .mwb XML is capped. Shrink the cap so the
    #    test stays cheap, then feed an entry larger than it.
    cap = mcdview.LIMITE_XML
    mcdview.LIMITE_XML = 4096
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('document.mwb.xml', b'<a>' + b'A' * (64 * 1024) + b'</a>')
        with tempfile.NamedTemporaryFile(suffix='.mwb', delete=False) as f:
            f.write(buf.getvalue())
            nom = f.name
        try:
            mcdview.analyser_mwb(nom)
            echecs.append('analyser_mwb: XML décompressé au-delà du cap accepté (zip bomb)')
        except SystemExit:
            pass
        finally:
            Path(nom).unlink(missing_ok=True)
    finally:
        mcdview.LIMITE_XML = cap

    # 3. a .dbm carrying a DTD is refused when reading table positions
    with tempfile.NamedTemporaryFile(suffix='.dbm', delete=False) as f:
        f.write(bombe)
        nom = f.name
    try:
        mcdview.positions_dbm(nom, {})
        echecs.append('positions_dbm: .dbm avec DTD accepté')
    except SystemExit:
        pass
    finally:
        Path(nom).unlink(missing_ok=True)

    # 3b. a malformed-but-valid-XML .dbm (a <table> missing its <schema>/
    # <position>, or a non-numeric coordinate) must not crash position reading
    for xml in (b'<dbmodel><table name="a"><position x="1" y="2"/></table></dbmodel>',
                b'<dbmodel><table name="a"><schema name="public"/></table></dbmodel>',
                b'<dbmodel><table name="a"><schema name="public"/>'
                b'<position x="NaN-ish" y="2"/></table></dbmodel>'):
        with tempfile.NamedTemporaryFile(suffix='.dbm', delete=False) as f:
            f.write(xml)
            nom = f.name
        try:
            mcdview.positions_dbm(nom, {'public.a': mcdview.nouvelle_table('public', 'a')})
        except Exception as e:
            echecs.append(f'positions_dbm: .dbm malformé plante ({type(e).__name__})')
        finally:
            Path(nom).unlink(missing_ok=True)

    # 4. a converter that hangs is killed by the timeout (shrunk for the test)
    delai = mcdview.DELAI_OUTIL
    mcdview.DELAI_OUTIL = 1
    try:
        t0 = time.perf_counter()
        try:
            mcdview.executer(['python3', '-c', 'import time; time.sleep(30)'])
            echecs.append('executer: aucun timeout sur un process bloqué')
        except SystemExit:
            pass
        if time.perf_counter() - t0 > 10:
            echecs.append('executer: le timeout n\'a pas tué le process à temps')
    finally:
        mcdview.DELAI_OUTIL = delai
    print('  OK  uploads : entités XML, zip bomb, DTD .dbm et timeout convertisseur')


def principal():
    echecs = []
    verifier_xss(echecs)
    verifier_dos(echecs)
    verifier_dos_natifs(echecs)
    verifier_uploads(echecs)
    if echecs:
        print('\nÉCHECS sécurité :')
        for e in echecs:
            print('  !', e)
        sys.exit(1)
    print('\nsécurité : XSS échappé, aucune bombe au-dessus du budget')


if __name__ == '__main__':
    principal()
