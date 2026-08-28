#!/usr/bin/env python3
"""Harvest a large local corpus of real-world schemas into tests/corpus/.

Two sources, via the GitHub code-search API (gh CLI must be authenticated):
- `structure.sql` files (Rails-style PostgreSQL dumps, one per repository);
- `.dbm` pgModeler models (sniffed for the <dbmodel XML root).

Files land in tests/corpus/github/ named owner__repo__file; nothing is
committed. Re-running skips what is already there. The code-search API only
indexes files under ~384 KiB on default branches — the big known schemas are
added by rapatrier.sh instead.
"""
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'github'

RECHERCHES = [
    ('filename:structure.sql language:SQL', '.sql', b'CREATE TABLE'),
    ('extension:dbm dbmodel', '.dbm', b'<dbmodel'),
]


def gh_api(chemin, **params):
    cmd = ['gh', 'api', '-X', 'GET', chemin]
    for c, v in params.items():
        cmd += ['-F' if isinstance(v, int) else '-f', f'{c}={v}']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print(f'  API refusée ({chemin}): {r.stderr.strip()[:150]}', file=sys.stderr)
        return None
    return json.loads(r.stdout)


def telecharger(url):
    with urllib.request.urlopen(url, timeout=30) as rep:
        return rep.read()


def principal():
    CORPUS.mkdir(parents=True, exist_ok=True)
    vus_depots = set()
    total = 0
    for requete, ext, aiguille in RECHERCHES:
        print(f'-- recherche : {requete}')
        for page in range(1, 11):
            resultat = gh_api('search/code', q=requete, per_page=100, page=page)
            if not resultat or not resultat.get('items'):
                break
            for item in resultat['items']:
                depot = item['repository']['full_name']
                if depot in vus_depots:
                    continue  # one file per repository is enough
                vus_depots.add(depot)
                nom = re.sub(r'[^\w.-]', '_', f"{depot}__{Path(item['path']).name}")
                if not nom.endswith(ext):
                    nom += ext
                cible = CORPUS / nom
                if cible.exists():
                    continue
                contenu = gh_api(item['url'])
                if not contenu or not contenu.get('download_url'):
                    continue
                try:
                    octets = telecharger(contenu['download_url'])
                except Exception as e:
                    print(f'  échec {depot}: {e}', file=sys.stderr)
                    continue
                if aiguille not in octets[:200000]:
                    continue  # wrong dialect or wrong .dbm format
                cible.write_bytes(octets)
                total += 1
                if total % 25 == 0:
                    print(f'  {total} fichiers...')
            # the code-search API is throttled around 10 queries/minute
            time.sleep(7)
    print(f'{total} nouveaux fichiers dans {CORPUS}')


if __name__ == '__main__':
    principal()
