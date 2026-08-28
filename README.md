# mcdview

<img src="logo.svg" width="96" align="right" alt="mcdview logo">

Interactive HTML explorer for a PostgreSQL data model. From a DDL file
(`CREATE TABLE ...`), mcdview generates a self-contained page — no server,
no dependency — to browse the model: overview of tables grouped by schema,
click a table to isolate it with its related tables, field detail panel,
search box.

**[Live demo](https://gheop.github.io/mcdview/exemples/mediatheque.html)** —
a fictional library model (12 tables, 3 schemas).

[![mcdview showing a table isolated with its related tables](docs/screenshot.webp)](https://gheop.github.io/mcdview/exemples/mediatheque.html)

## Usage

```bash
./mcdview.py model.sql
./mcdview.py model.sql -o explorer.html --titre "My project"
./mcdview.py model.dbm          # pgModeler model (needs pgmodeler-cli)
```

Then open the generated HTML file in a browser.

A `.dbm` input needs `pgmodeler-cli` in the PATH: mcdview delegates the
SQL generation to it (pgModeler resolves its relationships at export time),
and reuses the table positions drawn in the model.

In the page:

- **wheel**: zoom, **drag**: pan;
- **click a table**: isolates it with its related tables (the others fade
  out, the view re-frames) and shows its detail on the right — fields,
  types, NOT NULL, PK 🔑, clickable FK 🔗, table and column comments,
  list of referencing tables;
- **Escape** or "vue générale": back to the full, re-framed overview;
- **search** with table name autocompletion.

## Options

| Option | Effect |
|---|---|
| `-o, --sortie FILE` | Output HTML file (default: `<sql>.html`) |
| `--titre TEXT` | Title shown in the page (default: file name) |
| `--dbm FILE` | Reuse table positions from a pgModeler model instead of automatic layout |
| `--fk-audit REGEX` | Tag as "audit" the FKs whose constraint name matches: hidden by default, shown back with a checkbox |
| `--lang {fr,en}` | Language of the page UI (default: `fr`) |

Without `--dbm`, mcdview computes an automatic layout: one zone per schema,
tables arranged in balanced columns, related tables pulled together.

`--fk-audit` is for models where every table carries audit columns
(`created_by`, `modified_by`...) pointing to a users table: those FKs turn
that table into a hub linked to everything and clutter the graph.

## What mcdview reads from the DDL

- `CREATE TABLE [schema.]table (...)`: columns, types, NOT NULL, DEFAULT
  (tables without an explicit schema go to `public`);
- primary keys, inline (`CONSTRAINT ... PRIMARY KEY`) or added afterwards
  (`ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY`, `pg_dump -s` style);
- `ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ... REFERENCES ...`,
  including composite keys and targets without an explicit column list
  (resolved against the target's primary key);
- partitions (`PARTITION OF`, `ATTACH PARTITION`): hidden from the diagram,
  their constraints are carried back to the parent table;
- `COMMENT ON TABLE` and `COMMENT ON COLUMN`.

A `pg_dump -s` dump works as is. Views, functions and data are ignored.

## Examples

Each example ships as a `.sql` in `exemples/`; the browsable pages are
rebuilt by CI on every push:

| Model | | Contents | Source |
|---|---|---|---|
| **Médiathèque** — fictional French library, shows schemas zones, comments and audit FKs | [open](https://gheop.github.io/mcdview/exemples/mediatheque.html) | 12 tables, 3 schemas, 21 FKs | [mediatheque.sql](exemples/mediatheque.sql) |
| **Pagila** — DVD rental store (the PostgreSQL classic), with a partitioned `payment` table | [open](https://gheop.github.io/mcdview/exemples/pagila.html) | 16 tables, 22 FKs | [Pagila](https://github.com/devrimgunduz/pagila) (BSD) |
| **Northwind** — trading company, the historic Microsoft sample | [open](https://gheop.github.io/mcdview/exemples/northwind.html) | 14 tables, 13 FKs | [northwind_psql](https://github.com/pthom/northwind_psql) |
| **Chinook** — digital music store | [open](https://gheop.github.io/mcdview/exemples/chinook.html) | 11 tables, 11 FKs | [chinook-database](https://github.com/lerocha/chinook-database) (MIT) |

The real-world schemas are trimmed to their DDL (no data); each file keeps
its source and license in a header comment. To regenerate, e.g.:

```bash
./mcdview.py exemples/mediatheque.sql --titre "Médiathèque (démo)" --fk-audit '_idmodificateur_fk$' --lang en
./mcdview.py exemples/pagila.sql --titre "Pagila (DVD rental)" --lang en
```

## Development

Plain Python 3, no dependency. All the rendering lives in
`templates/explorateur.html` (inline CSS/JS); the data is injected as JSON
in place of `__DONNEES__`.

## Changelog

### v0.4.0 — pgModeler .dbm input, CI-built pages (2026-08-28)

- A `.dbm` pgModeler model can be passed directly as input: the SQL is
  produced by `pgmodeler-cli` and the table positions drawn in the model
  are reused
- The example pages are rebuilt by GitHub Actions on every push instead of
  being committed
- Code comments, docstrings and CLI output translated to English

### v0.3.0 — Wider DDL support, real-world examples (2026-08-28)

- The parser now accepts unqualified tables (defaulting to the `public`
  schema), an opening parenthesis on its own line, primary keys declared
  via `ALTER TABLE` (`pg_dump -s` style), composite foreign keys, FK targets
  without a column list, and partitioned tables (partitions are folded into
  their parent)
- 3 real-world example models with browsable pages: Pagila, Northwind,
  Chinook

### v0.2.0 — English UI (2026-08-28)

- `--lang {fr,en}` option: language of the generated page's interface
  (search box, help text, detail panel labels)
- The live demo now uses the English UI

### v0.1.1 — Public release (2026-08-28)

- Fictional library demo (`exemples/mediatheque.sql`) with a live version
  on GitHub Pages
- README in English, screenshot
- Published on GitHub

### v0.1.0 — First standalone version (2026-08-27)

- Automatic table layout (one zone per schema, balanced columns, related
  tables pulled together) — the pgModeler `.dbm` becomes optional
- `--titre`, `--fk-audit`, `--dbm`, `-o` options
- SVG logo, "audit FK" checkbox hidden when no FK matches
