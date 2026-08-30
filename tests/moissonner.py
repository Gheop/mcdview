#!/usr/bin/env python3
"""Harvest a large local corpus of real-world schemas into tests/corpus/github/.

Uses the GitHub code-search API (gh CLI must be authenticated). Many targeted
queries per format/dialect maximise repository diversity (one file per repo).
Content is fetched from the raw CDN (derived from the search hit's html_url),
so only the search calls count against the stricter code-search rate limit.

Files land named owner__repo__file; nothing is committed. Re-running skips what
is already there, so it resumes. The code-search API only indexes files under
~384 KiB on default branches; the big known schemas come from rapatrier.sh.

Usage: moissonner.py [--max N] [--par-requete P]
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'github'

# (query, extension, required-substring-in-content). The needle biases toward
# the right dialect/format and rejects false positives.
RECHERCHES = [
    # --- PostgreSQL / generic SQL: shard by common table names to hit ---
    # different repositories (code search caps a query at 1000 hits)
    ('filename:structure.sql language:SQL', '.sql', b'CREATE TABLE'),
    ('filename:schema.sql CREATE TABLE language:SQL', '.sql', b'CREATE TABLE'),
    ('pg_dump CREATE TABLE language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE users language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE orders language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE products language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE customers language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE accounts language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE employees language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE invoices language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE categories language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE payments language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE sessions language:SQL', '.sql', b'CREATE TABLE'),
    ('SERIAL PRIMARY KEY CREATE TABLE language:SQL', '.sql', b'SERIAL'),
    ('bigserial REFERENCES language:SQL', '.sql', b'REFERENCES'),
    ('ALTER TABLE ADD CONSTRAINT FOREIGN KEY language:SQL', '.sql', b'FOREIGN KEY'),
    # --- MySQL / MariaDB ---
    ('ENGINE InnoDB CREATE TABLE language:SQL', '.sql', b'ENGINE'),
    ('AUTO_INCREMENT PRIMARY KEY language:SQL', '.sql', b'AUTO_INCREMENT'),
    ('mysqldump CREATE TABLE language:SQL', '.sql', b'ENGINE'),
    ('DEFAULT CHARSET utf8mb4 language:SQL', '.sql', b'CHARSET'),
    # --- SQLite ---
    ('AUTOINCREMENT CREATE TABLE language:SQL', '.sql', b'AUTOINCREMENT'),
    ('filename:schema.sql AUTOINCREMENT', '.sql', b'AUTOINCREMENT'),
    # --- Oracle ---
    ('VARCHAR2 CREATE TABLE language:SQL', '.sql', b'VARCHAR2'),
    ('NUMBER NOT NULL CREATE TABLE language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE tablespace language:SQL', '.sql', b'CREATE TABLE'),
    # --- SQL Server (tsql) ---
    ('NVARCHAR IDENTITY CREATE TABLE language:SQL', '.sql', b'IDENTITY'),
    ('CREATE TABLE dbo language:SQL', '.sql', b'CREATE TABLE'),
    ('UNIQUEIDENTIFIER CREATE TABLE language:SQL', '.sql', b'UNIQUEIDENTIFIER'),
    # --- ClickHouse / Snowflake / BigQuery / DuckDB ---
    ('ENGINE MergeTree CREATE TABLE language:SQL', '.sql', b'MergeTree'),
    ('CREATE TABLE cluster by language:SQL', '.sql', b'CREATE TABLE'),
    ('CREATE TABLE STORED AS PARQUET language:SQL', '.sql', b'CREATE TABLE'),
    # --- pgModeler .dbm ---
    ('pgmodeler-ver extension:dbm', '.dbm', b'<dbmodel'),
    ('dbmodel pgmodeler extension:dbm', '.dbm', b'<dbmodel'),
    # --- dbdiagram.io .dbml ---
    ('Table Ref extension:dbml', '.dbml', b'Table'),
    ('extension:dbml Ref:', '.dbml', b'Ref'),
    ('extension:dbml Table', '.dbml', b'Table'),
    # --- Prisma ---
    ('filename:schema.prisma model', '.prisma', b'model '),
    ('datasource db provider extension:prisma', '.prisma', b'model '),
    ('generator client extension:prisma', '.prisma', b'model '),
    # --- Rails schema.rb ---
    ('filename:schema.rb create_table', '.rb', b'create_table'),
    ('ActiveRecord Schema define create_table', '.rb', b'create_table'),
    # --- Mermaid erDiagram ---
    ('erDiagram extension:mmd', '.mmd', b'erDiagram'),
    ('erDiagram extension:mermaid', '.mermaid', b'erDiagram'),
    ('erDiagram PK FK extension:md', '.md', b'erDiagram'),
    ('mermaid erDiagram extension:md', '.md', b'erDiagram'),
    # --- Drizzle schema.ts ---
    ('pgTable drizzle-orm extension:ts', '.ts', b'Table('),
    ('mysqlTable drizzle-orm extension:ts', '.ts', b'Table('),
    ('sqliteTable drizzle-orm extension:ts', '.ts', b'Table('),
    ('filename:schema.ts pgTable', '.ts', b'Table('),
]


def gh_api(chemin, **params):
    cmd = ['gh', 'api', '-X', 'GET', chemin]
    for c, v in params.items():
        cmd += ['-F' if isinstance(v, int) else '-f', f'{c}={v}']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        msg = r.stderr.strip()[:150]
        print(f'  API refusée ({chemin}): {msg}', file=sys.stderr)
        return None, ('rate' in msg.lower() or '403' in msg)
    return json.loads(r.stdout), False


def url_raw(item):
    # html_url is https://github.com/{owner}/{repo}/blob/{ref}/{path}
    h = item.get('html_url', '')
    m = re.match(r'https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)', h)
    if not m:
        return None
    o, r, ref, path = m.groups()
    # the path may contain spaces or other characters unsafe in a URL
    path = urllib.parse.quote(path)
    return f'https://raw.githubusercontent.com/{o}/{r}/{ref}/{path}'


def telecharger(url):
    with urllib.request.urlopen(url, timeout=30) as rep:
        return rep.read()


def principal():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max', type=int, default=100000, help='stop after N new files')
    ap.add_argument('--par-requete', type=int, default=10, help='pages per query (×100)')
    args = ap.parse_args()

    CORPUS.mkdir(parents=True, exist_ok=True)
    vus_depots = set()
    # a repo already harvested in a previous run: seed dedup from filenames
    for f in CORPUS.glob('*'):
        vus_depots.add(f.name.split('__')[0])
    total = 0
    for requete, ext, aiguille in RECHERCHES:
        if total >= args.max:
            break
        print(f'-- recherche : {requete}  (total {total})')
        for page in range(1, args.par_requete + 1):
            resultat, limite = gh_api('search/code', q=requete, per_page=100, page=page)
            if limite:
                print('  limite de débit atteinte, pause 60 s')
                time.sleep(60)
                continue
            if not resultat or not resultat.get('items'):
                break
            for item in resultat['items']:
                depot = item['repository']['full_name']
                marque = re.sub(r'[^\w.-]', '_', depot.replace('/', '_'))
                if marque in vus_depots:
                    continue  # one file per repository is enough
                url = url_raw(item)
                if not url:
                    continue
                nom = re.sub(r'[^\w.-]', '_', f"{depot}__{Path(item['path']).name}")
                if not nom.endswith(ext):
                    nom += ext
                cible = CORPUS / nom
                if cible.exists():
                    vus_depots.add(marque)
                    continue
                try:
                    octets = telecharger(url)
                except Exception as e:
                    print(f'  échec {depot}: {e}', file=sys.stderr)
                    continue
                if aiguille not in octets[:300000]:
                    continue  # wrong dialect/format
                vus_depots.add(marque)
                cible.write_bytes(octets)
                total += 1
                if total % 50 == 0:
                    print(f'  {total} fichiers...')
                if total >= args.max:
                    break
            if total >= args.max:
                break
            time.sleep(6)  # code-search API is throttled ~10 queries/minute
    print(f'{total} nouveaux fichiers dans {CORPUS}')


if __name__ == '__main__':
    principal()
