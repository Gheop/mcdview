#!/usr/bin/env python3
"""Generate synthetic DDL files of controlled sizes into tests/corpus/synthese/.

Deterministic (seeded) models: N tables spread over a few schemas, 3-20
columns each, ~1.5 FK per table pointing at earlier tables, comments on a
third of them. Used to measure how parsing, layout and page size scale.
"""
import random
from pathlib import Path

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'synthese'
TAILLES = [10, 50, 100, 250, 500, 1000, 2000, 5000]
TYPES = ['integer', 'bigint', 'text', 'character varying(120)', 'boolean',
         'date', 'timestamp without time zone', 'numeric(12,2)', 'uuid', 'jsonb']


def generer(n):
    alea = random.Random(n)
    schemas = [f's{i}' for i in range(max(1, min(8, n // 40)))]
    lignes = [f'-- synthetic model: {n} tables', '']
    lignes += [f'CREATE SCHEMA {s};' for s in schemas] + ['']
    tables = []
    for i in range(n):
        sch = alea.choice(schemas)
        nom = f'table_{i:04d}'
        tables.append((sch, nom))
        cols = [f'    id_{nom} integer NOT NULL']
        for j in range(alea.randint(2, 19)):
            defaut = " DEFAULT now()" if alea.random() < .1 else ''
            nn = ' NOT NULL' if alea.random() < .4 else ''
            cols.append(f'    champ_{j:02d} {alea.choice(TYPES)}{defaut}{nn}')
        cols.append(f'    CONSTRAINT {nom}_pk PRIMARY KEY (id_{nom})')
        lignes += [f'CREATE TABLE {sch}.{nom} (', ',\n'.join(cols), ');', '']
        if alea.random() < .33:
            lignes.append(f"COMMENT ON TABLE {sch}.{nom} IS 'Synthetic table number {i}.';")
    for i, (sch, nom) in enumerate(tables):
        for _ in range(alea.choice((0, 1, 1, 2, 3))):
            if i == 0:
                break
            csch, cnom = tables[alea.randrange(i)]
            lignes.append(
                f'ALTER TABLE {sch}.{nom} ADD CONSTRAINT {nom}_vers_{cnom}_fk '
                f'FOREIGN KEY (champ_00) REFERENCES {csch}.{cnom} (id_{cnom});')
    return '\n'.join(lignes) + '\n'


def principal():
    CORPUS.mkdir(parents=True, exist_ok=True)
    for n in TAILLES:
        cible = CORPUS / f'synthese_{n:05d}.sql'
        cible.write_text(generer(n))
        print(f'{cible.name} : {cible.stat().st_size // 1024} KiB')


if __name__ == '__main__':
    principal()
