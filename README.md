# mcdview

<img src="logo.svg" width="96" align="right" alt="logo mcdview">

Explorateur HTML interactif d'un modèle de données PostgreSQL. À partir d'un
fichier DDL (`CREATE TABLE ...`), mcdview génère une page autonome — aucun
serveur, aucune dépendance — où l'on navigue dans le modèle : vue d'ensemble
des tables par schéma, clic pour isoler une table avec ses tables liées,
panneau de détail des champs, recherche.

## Utilisation

```bash
./mcdview.py modele.sql
./mcdview.py modele.sql -o explorateur.html --titre "Mon projet"
```

Puis ouvrir le fichier HTML produit dans un navigateur.

Dans la page :

- **molette** : zoom, **glisser** : déplacement;
- **clic sur une table** : l'isole avec ses tables liées (les autres
  disparaissent, la vue se cadre) et affiche son détail à droite — champs,
  types, NOT NULL, PK 🔑, FK 🔗 cliquables, commentaires de tables et de
  colonnes, liste des tables qui la référencent;
- **Échap** ou « vue générale » : retour au plan complet, recadré;
- **recherche** avec autocomplétion des noms de tables.

## Options

| Option | Effet |
|---|---|
| `-o, --sortie FICHIER` | Fichier HTML produit (défaut : `<sql>.html`) |
| `--titre TEXTE` | Titre affiché dans la page (défaut : nom du fichier) |
| `--dbm FICHIER` | Reprend les positions des tables d'un modèle pgModeler au lieu du placement automatique |
| `--fk-audit REGEX` | Classe « audit » les FK dont le nom de contrainte matche : masquées par défaut, réaffichables d'une case à cocher |

Sans `--dbm`, mcdview calcule un placement automatique : une zone par schéma,
tables rangées en colonnes équilibrées, les tables liées rapprochées.

## Ce que mcdview lit dans le DDL

- `CREATE TABLE schema.table (...)` : colonnes, types, NOT NULL, DEFAULT,
  `CONSTRAINT ... PRIMARY KEY`;
- `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`;
- `COMMENT ON TABLE` et `COMMENT ON COLUMN`.

Les tables doivent être qualifiées par leur schéma. Un dump `pg_dump -s`
qualifié convient.

## Exemple

`exemples/mediatheque.html` est généré depuis `exemples/mediatheque.sql`,
un modèle fictif de médiathèque (12 tables, 3 schémas, 21 FK dont 7 d'audit) :

```bash
./mcdview.py exemples/mediatheque.sql --titre "Médiathèque (démo)" --fk-audit '_idmodificateur_fk$'
```

## Développement

Python 3 standard, aucune dépendance. Le rendu vit dans
`templates/explorateur.html` (CSS/JS inline), les données y sont injectées en
JSON à la place de `__DONNEES__`.

## Changelog

### v0.1.0 — Première version autonome (2026-08-27)

- Extraction du projet Gest'EA pour en faire un outil générique
- Placement automatique des tables (une zone par schéma, colonnes équilibrées, tables liées rapprochées) — le `.dbm` pgModeler devient optionnel
- Options `--titre`, `--fk-audit`, `--dbm`, `-o`
- Logo SVG, case « FK d'audit » masquée quand aucune FK ne matche
