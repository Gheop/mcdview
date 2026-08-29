# mcdview

<img src="logo.svg" width="96" align="right" alt="mcdview logo">

[![hosted at mcdview.dev](https://img.shields.io/badge/hosted-mcdview.dev-2563eb)](https://mcdview.dev/)
[![live demo](https://img.shields.io/badge/demo-live-22c55e)](https://gheop.github.io/mcdview/)
[![ci](https://github.com/Gheop/mcdview/actions/workflows/ci.yml/badge.svg)](https://github.com/Gheop/mcdview/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-64748b)](LICENSE)
![no dependencies](https://img.shields.io/badge/dependencies-none-64748b)

Interactive HTML explorer for a SQL data model. From a DDL file
(`CREATE TABLE ...`), mcdview generates a self-contained page — no server,
no dependency — to browse the model: overview of tables grouped by schema,
click a table to isolate it with its related tables, field detail panel,
search box.

PostgreSQL is read out of the box with zero dependencies; MySQL/MariaDB,
SQLite and ~15 other dialects are read when the optional
[sqlglot](https://github.com/tobymao/sqlglot) package is installed.

**Try it without installing anything: [mcdview.dev](https://mcdview.dev/)** —
drop a `.sql` or `.dbm` file and get a shareable link to your model's page.

**[Live demo](https://gheop.github.io/mcdview/exemples/mediatheque.html)** —
a fictional library model (12 tables, 3 schemas).

[![mcdview showing a table isolated with its related tables](docs/screenshot.webp)](https://gheop.github.io/mcdview/exemples/mediatheque.html)

## Usage

```bash
./mcdview.py model.sql
./mcdview.py model.sql -o explorer.html --titre "My project"
./mcdview.py model.dbm          # pgModeler model (needs pgmodeler-cli)
./mcdview.py model.dbml         # dbdiagram.io model (needs @dbml/cli)
./mcdview.py schema.prisma      # Prisma schema (needs prisma)
./mcdview.py model.mwb          # MySQL Workbench model (native, no tool)
./mcdview.py db/schema.rb       # Rails schema (native, no tool)
./mcdview.py diagram.mmd        # Mermaid erDiagram (native, .mmd/.md)
./mcdview.py schema.ts          # Drizzle ORM schema (native, no tool)
./mcdview.py --db postgresql://user:pw@host/db   # dump a live database (CLI only)
./mcdview.py new.sql --diff old.sql              # compare two versions of a model
```

Then open the generated HTML file in a browser.

`--diff BASELINE` compares the main model against an older one (each may be
any supported format) and colors the result: tables, columns and foreign keys
that were **added** show green, **removed** ones red and struck through
(kept on the diagram so you can see what went), **changed** ones amber. A
legend appears at the bottom with per-category counts and a "N touched"
button that hides the unchanged tables to frame just what moved. Handy for
reviewing a migration before running it.

`--db` reads the schema straight from a running database instead of a file:
`postgresql://…` shells out to `pg_dump -s`, `mysql://…` to `mysqldump
--no-data`. It is a **command-line-only** feature — never wire it behind a
public service, since it would let a caller point the process at any host it
can reach (SSRF).

A `.dbm` input needs `pgmodeler-cli` in the PATH: mcdview delegates the
SQL generation to it (pgModeler resolves its relationships at export time),
and reuses the table positions drawn in the model.

In the page:

- **wheel**: zoom, **drag**: pan;
- **hover a table**: lights up its foreign-key links;
- **click a table**: isolates it with its related tables (the others fade
  out, the view re-frames) and shows its detail on the right — fields,
  types, NOT NULL, DEFAULT, PK 🔑, clickable FK 🔗, table and column
  comments, list of referencing tables; the URL gets a `#schema.table`
  permalink that reopens straight on that table;
- **drag a table** to rearrange the diagram, the links follow live;
- **"rearrange" button**: a force-directed relayout that spreads the tables
  to unclutter the links (disabled above 400 tables, where it would be slow);
- **schema chips** (bottom-left, when there are several schemas): click to
  frame that schema's zone;
- **Escape** or "overview": back to the full, re-framed overview;
- **search** with table name autocompletion.

## Options

| Option | Effect |
|---|---|
| `-o, --sortie FILE` | Output HTML file (default: `<sql>.html`) |
| `--titre TEXT` | Title shown in the page (default: file name) |
| `--dbm FILE` | Reuse table positions from a pgModeler model instead of automatic layout |
| `--fk-audit REGEX` | Tag as "audit" the FKs whose constraint name matches: hidden by default, shown back with a checkbox |
| `--lang {fr,en}` | Language of the page UI (default: `fr`) |
| `--dialect NAME` | Input SQL dialect (default: `auto`); non-PostgreSQL needs `sqlglot` |
| `--home-url URL` | Wrap the header logo in a link to this URL |
| `--logo FILE` | Replace the header logo with this image (svg/png/jpg…, shown 22×22) |
| `--credit TEXT` | Discreet attribution badge, bottom-right (off by default) |
| `--credit-url URL` | Make the `--credit` badge a link to this URL |
| `--db URL` | Read a live database's schema instead of a file (`postgresql://…` via `pg_dump`, `mysql://…` via `mysqldump`); CLI only |
| `--diff BASELINE` | Compare against an older model (any supported format); added/removed/changed tables, columns and FKs are colored |
| `--summary FILE` | With `--diff`: also write a JSON summary of the changes (counts + change list) to `FILE` |

Without `--dbm`, mcdview computes an automatic layout: one zone per schema,
tables arranged in balanced columns, related tables pulled together.

## Dialects

PostgreSQL uses the built-in parser (no dependency). For any other dialect,
`pip install sqlglot` and mcdview reads it — MySQL/MariaDB, SQLite, SQL Server
(`tsql`), Oracle, DuckDB, Snowflake, BigQuery, Redshift, ClickHouse, Trino,
Spark, Hive. `--dialect auto` (the default) uses the PostgreSQL parser first
and, when it finds no table, tries several sqlglot dialects and keeps the one
that parses the most tables; pass `--dialect mysql` (etc.) to force one. Model files are read through an upstream converter (an optional dependency,
like the SQL dialects): pgModeler `.dbm` via `pgmodeler-cli`,
dbdiagram.io `.dbml` via `@dbml/cli`, and Prisma `schema.prisma` via the
`prisma` CLI. MySQL Workbench `.mwb`, Rails `db/schema.rb`, Mermaid `erDiagram`
(`.mmd`/`.mermaid`/`.md`) and Drizzle ORM `schema.ts` are read **natively**
(no external tool needed). Other proprietary formats (Navicat,
ERwin, Oracle SQL Developer Data Modeler…) have no reliable converter: export
their SQL instead (Workbench-style Forward Engineer), which mcdview reads.

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

### Tested at scale

The harness under `tests/` last ran mcdview over **839 schemas**: 529
real-world `.sql` and 296 pgModeler `.dbm` harvested from public GitHub
repositories, plus synthetic models up to 5000 tables. Results: **zero
crashes**; every PostgreSQL schema produced a valid page (17,449 tables and
19,788 FKs in total, DOM-verified on a sample in headless Chrome); MySQL
and SQLite inputs are detected and get a clear hint; 99% of the loadable
`.dbm` models convert (a `--fix-model` repair pass catches models saved by
older pgModeler versions). Median page build: 4 ms; worst case (5000
tables, 3.2 MB of DDL): 0.6 s.

Model data (names, types, comments, defaults) is HTML-escaped and the JSON
data island escapes every `<`, so a hostile schema cannot inject markup or
script into the page — this matters when generating pages from files you did
not write. `tests/test_securite.py` checks the escaping and a ReDoS/DoS time
budget on hostile inputs (`tests/malveillant/`).

`tests/tester.py` runs mcdview end-to-end on every committed example and
every pgModeler sample model, checks pinned table/FK counts and times each
run; `tests/grand_banc.py` runs the whole local corpus (`--strict` fails on
any exception, `--dbm` adds the pgModeler models, `--chrome N` DOM-validates
N sampled pages); `tests/rapatrier.sh`, `tests/moissonner.py` and
`tests/generer_synthetique.py` fill the local, uncommitted corpus.
`tests/test_dialectes.py` parses committed non-PostgreSQL fixtures, including
`tests/dialectes/boutique.mariadb.sql` — a frozen `mysqldump --no-data` dump
(backtick quoting, named inline `CONSTRAINT` FKs, a composite primary key)
that pins the exact SQL a `--db mysql://…` run feeds the parser, so the
`--db` path stays covered without a live server. The pre-commit hook
(`git config core.hooksPath .githooks`) runs the pinned regression, the
security suite and the strict corpus campaign.

## License

[MIT](LICENSE). The example schemas keep their own licenses, noted in each
file's header.

## Changelog

### v0.21.0 — Diff polish, rename detection, column search (2026-08-29)

- The diff detail panel now shows a retyped column as `old → new` (the old
  type struck through).
- Small single-schema models lay out as a roughly square block instead of a
  tall vertical band.
- Rename detection: a table dropped and one added with the same set of column
  names is shown as a rename ("renamed from X", amber) rather than a
  remove+add pair, and a foreign key untouched apart from the rename stays
  unchanged. The JSON summary carries `renamed_from`.
- Search now matches column names too (`table.column` or a bare column name):
  it isolates the table and highlights the row.

### v0.20.2 — JSON diff summary (2026-08-29)

- `--summary FILE` (with `--diff`) writes a machine-readable JSON summary of
  the changes: per-category counts (tables/columns/FKs added, removed,
  changed) and the change list, with the previous type kept for retyped
  columns (`"was": "numeric(10,2)"`). Lets a caller show change badges or a
  version timeline without parsing the HTML.

### v0.20.1 — Diff legend counts and "touched only" filter (2026-08-29)

- The diff legend now shows how many tables were added, changed and removed,
  and a "N touched" button hides the unchanged tables to frame just the ones
  that moved. "Overview" / Escape brings everything back.

### v0.20.0 — Schema diff (2026-08-29)

- `--diff BASELINE` compares the model against an older version (any supported
  format on either side) and colors the diagram: tables, columns and foreign
  keys that were added (green), removed (red, struck through, kept on the
  diagram), or changed (amber). A legend shows the key. Useful to review a
  migration visually before applying it.
- Internals: the seven parsers now share a single `charger()` dispatch and the
  `nouvelle_table` / `nouvelle_colonne` factories, so every format flows
  through the same code — which is what makes the diff work across all of them.

### v0.19.3 — Harden the untrusted-upload surface (2026-08-29)

- Model XML (`.mwb`, `.dbm`) is refused if it declares a DTD or entities, the
  vector for entity-expansion ("billion laughs") and XXE attacks the stdlib
  XML parser does not block on its own.
- The `.mwb` archive is read through a size cap, so a tiny file cannot
  decompress into gigabytes (zip bomb).
- Every external converter (`pgmodeler-cli`, `dbml2sql`, `prisma`,
  `pg_dump`/`mysqldump`) runs under a timeout and is killed if it hangs.
- `tests/test_securite.py` covers all four (generated on the fly, like the
  ReDoS bombs). This matters for a service that renders files it did not write.

### v0.19.2 — Fuller Mermaid erDiagram parsing (2026-08-29)

- A crow's-foot cardinality (`o{`, `}o`) is no longer mistaken for an entity
  block, which previously invented a phantom one-letter table.
- Attribute comments (`int id PK "SERIAL"`) become column comments, shown in
  the detail panel; `%%` comment lines and a `direction` directive inside an
  entity block are ignored instead of read as columns; comma-separated
  attribute keys (`PK, FK`) are accepted.
- Validated on 113 real erDiagram files (raw `.mmd` and inside Markdown
  fences): 918 tables, 1002 FKs, zero bogus columns.

### v0.19.1 — Links follow tables during "rearrange" (2026-08-29)

- "Rearrange" now redraws the FK links on every frame while the tables glide
  to their new positions, instead of leaving them behind and snapping them
  into place once the CSS transition ends.

### v0.19.0 — Read a live database via --db (2026-08-28)

- `--db postgresql://…` / `--db mysql://…`: dump a running database's schema
  (`pg_dump -s` for PostgreSQL, `mysqldump --no-data` for MySQL/MariaDB) and
  render it, no intermediate file needed. The positional model argument
  becomes optional; the page title defaults to the database name.
- MySQL passwords go through the `MYSQL_PWD` environment variable, never on
  the process command line.
- FK constraint names are now recovered on the MySQL/sqlglot path (they hang
  off the wrapping `CONSTRAINT` node), so `--fk-audit` works on MySQL and
  MariaDB models too.
- **Command-line only.** This feature must not be exposed on a public
  service: it would let a caller make the process connect to any host it can
  reach (SSRF). The hosted site keeps taking uploaded files only.

### v0.18.0 — Drizzle ORM schema.ts input (2026-08-28)

- Read Drizzle ORM `schema.ts` natively: each `pgTable`/`mysqlTable`/
  `sqliteTable` becomes a table, its `type("col")` fields columns (with
  `.primaryKey()`/`.notNull()`), and `.references(() => t.col)` the foreign
  keys; commented-out definitions are ignored

### v0.17.0 — Mermaid erDiagram input (2026-08-28)

- Read Mermaid `erDiagram` natively, raw `.mmd`/`.mermaid` or inside a
  ```` ```mermaid ```` fence in a `.md`: entities become tables, attributes
  columns (PK marker → key), each relationship an FK from the crow's-foot
  ("many") side to the "one" side

### v0.16.0 — Rails schema.rb input (2026-08-28)

- Read Rails `db/schema.rb` natively (the `create_table` / `add_foreign_key`
  DSL is regular): the implicit `id` primary key, column types, and foreign
  keys (default column resolved by singularizing the target table)

### v0.15.0 — MySQL Workbench .mwb input (2026-08-28)

- Read MySQL Workbench `.mwb` models natively — the file is a zip whose
  `document.mwb.xml` (GRT object tree) is parsed with the standard library,
  no external tool: schemas, tables, column types, primary and foreign keys

### v0.14.0 — Prisma schema input (2026-08-28)

- Read Prisma `schema.prisma` models, converted to SQL by `prisma migrate
  diff`; the schema's provider (postgres/mysql/sqlite/sqlserver) is detected
  automatically, MongoDB schemas are reported as unsupported
- The PK/FK parsers now accept double-quoted constraint names
  (`CONSTRAINT "x_pkey" PRIMARY KEY ...`), as emitted by Prisma and modern tools

### v0.13.0 — DBML input (2026-08-28)

- Read dbdiagram.io `.dbml` models (converted to SQL by `@dbml/cli`), the
  same upstream-converter pattern as `.dbm`
- The FK parser now also reads unnamed constraints (`ADD FOREIGN KEY ...`
  without `CONSTRAINT name`), which dbml2sql and some dumps emit

### v0.12.0 — Attribution badge, safer link URLs (2026-08-28)

- `--credit TEXT` / `--credit-url URL`: a slanted rubber-stamp attribution
  badge (mcdview logo + text) in the bottom-right corner, off by default;
  text escaped, optional link
- `--home-url` and `--credit-url` now reject dangerous URL schemes
  (`javascript:`, `data:`…), keeping only http(s)/mailto/relative links

### v0.11.0 — SQL Server routing and ALTER ADD COLUMN (2026-08-28)

- SQL Server DDL (`[bracket]` identifiers) is routed to the sqlglot tsql
  parser instead of being mangled by the PostgreSQL parser
- `ALTER TABLE ... ADD [COLUMN] name type` columns are now read, not just
  the ones inside the `CREATE TABLE` body
- Both found by running the content-invariant test over a larger, more
  dialect-diverse harvested corpus

### v0.10.1 — Case-insensitive key matching (2026-08-28)

- PK/FK column names are matched to columns case-insensitively (unquoted SQL
  identifiers are case-insensitive), so a `PLAYERID` primary key on a
  `playerID` column shows its 🔑 instead of being dropped as a phantom —
  found by the content-invariant test on a wider harvested corpus

### v0.10.0 — Header logo link and custom logo (2026-08-28)

- `--home-url URL`: the header logo becomes a link (e.g. back to the
  hosting site); URL escaped, nothing changes when the option is absent
- `--logo FILE`: replace the header logo with your own image (svg/png/jpg…),
  embedded as an `<img>` data URI so a third-party SVG cannot run scripts

### v0.9.5 — Parser fixes from content-invariant testing (2026-08-28)

- Strip quoting from column names in PK/FK lists, so a `` `id` `` or
  `"timestamp"` primary key no longer becomes a phantom (unmatched) key
- Read quoted table/schema names (`CREATE TABLE "accounts"`), so double-quoted
  DDL (e.g. Drizzle output) is parsed instead of dropped entirely
- Route obviously non-PostgreSQL files (backticks) to sqlglot rather than
  letting the regex parser mangle them
- New `tests/test_invariants.py`: checks the parsed model is internally
  consistent (no empty types, no phantom PK columns, FK endpoints exist)

### v0.9.4 — Auto-dialect tries several parsers (2026-08-28)

- When PostgreSQL yields no table, `--dialect auto` now tries several sqlglot
  dialects and keeps the one parsing the most tables, instead of guessing a
  single one — recovers files that were mis-detected (a 28-table model was
  read as the wrong dialect and dropped entirely)

### v0.9.3 — Square overview for huge schemas (2026-08-28)

- The automatic layout now sizes each schema's column height for a roughly
  square zone, so a large single-schema model no longer stretches into an
  unreadable horizontal band (a 1066-table model went from a 41:1 strip to
  1.4:1); small models are unchanged

### v0.9.2 — Dialect polish (2026-08-28)

- The detected dialect is shown in the toolbar counter for non-PostgreSQL
  models (e.g. `12 tables · 21 FK · mysql`)
- sqlglot column types are lowercased to match the PostgreSQL parser
  (`INT(11)` → `int(11)`), keeping string literals intact

### v0.9.1 — Isolated view no longer overlaps (2026-08-28)

- When isolating a table, the star of related tables now sizes its radius to
  the tables involved and runs a de-overlap pass (centre kept fixed), so a
  large neighbour (e.g. a 40-column table) no longer covers the isolated one

### v0.9.0 — Multi-dialect input via sqlglot (2026-08-28)

- Read MySQL/MariaDB, SQLite and ~15 other dialects through the optional
  `sqlglot` backend (PostgreSQL stays dependency-free); `--dialect` flag,
  `auto` sniffs and falls back. On the harvested corpus, files that produced
  no page dropped from 257 to 18
- Dialect fixtures and test (`tests/test_dialectes.py`), sqlglot wired into
  CI and the pre-commit hook

### v0.8.5 — Hosted at mcdview.dev (2026-08-28)

- Link to the hosted service at [mcdview.dev](https://mcdview.dev/): upload a
  `.sql` or `.dbm` and get a shareable link, no install needed
- README badges (hosted, demo, CI, license), repository homepage and topics
  for discoverability

### v0.8.4 — Rearrange no longer overlaps big tables (2026-08-28)

- The rearrange layout now sizes each edge to the two tables it links (a
  constant target was pulling wide tables into each other), reins in weakly
  linked tables with a gravity term and a bounded repulsion range, and ends
  with a de-overlap pass — a 69-table model went from 60 overlapping pairs
  to zero, in a compact frame

### v0.8.3 — Own the pgmodeler-cli image, reliable .dbm CI (2026-08-28)

- `docker/pgmodeler-cli/` + `image.yml` build and publish
  `ghcr.io/gheop/pgmodeler-cli` (Fedora 44 + pgModeler 1.2.2, plus a `-node`
  variant for `container:` jobs); the tag is the pgModeler version baked in
- The CI `.dbm` job now runs inside that pinned image (fixed version → stable
  counts) and is blocking instead of best-effort

### v0.8.2 — Tolerate pgmodeler-cli fix-model segfault (2026-08-28)

- `--fix-model` on pgmodeler-cli 1.2.2 writes the repaired `.dbm` in full,
  then segfaults while freeing the model (memory-layout dependent, systematic
  in containers). mcdview now judges the repair by the output file, not the
  exit code, so old `.dbm` models convert inside a container

### v0.8.1 — CI test pipeline (2026-08-28)

- CI now runs on every push and pull request: Python error linting
  (`ruff --select F,E9`, `py_compile`), the pinned regression, the security
  suite, the strict corpus campaign, HTML structure validation and a
  headless-Chrome DOM check on the generated example pages; deploy to Pages
  only runs on `main` after the tests pass
- `tests/valider_html.py` validates a page's structure and data island
- A best-effort `.dbm` job installs pgmodeler-cli on the runner (never
  blocks a PR)

### v0.8.0 — Rearrange button (2026-08-28)

- "Rearrange" button: a dependency-free force-directed relayout
  (Fruchterman-Reingold) that spreads tables to reduce link crossings —
  on a 69-table model with its audit FKs hidden, crossings dropped from
  662 to 217. Disabled above 400 tables (the O(n²) pass would freeze the tab)

### v0.7.0 — Hover, permalinks, hardening (2026-08-28)

- Hover a table to light up its links; `#schema.table` permalinks that
  reopen on the right table; DEFAULT values in the detail panel; table
  comments as tooltips; a table/FK counter in the toolbar
- Security: all injected model data is HTML-escaped and the JSON island
  escapes `<`, closing an XSS vector; the CREATE TABLE body is now bounded
  by string search instead of a lazy regex, killing a ReDoS (a 830 KiB
  malformed file went from 13 s to 0.3 s)
- Security test suite and a strict corpus campaign wired into the
  pre-commit hook

### v0.6.1 — .dbm repair fallback (2026-08-28)

- When pgmodeler-cli refuses a `.dbm` (saved by an older pgModeler), mcdview
  now retries through `--fix-model` before giving up — on the harvested
  corpus this takes the refusal rate from 136/296 down to 2/296
- Campaign results published in the README ("Tested at scale")

### v0.6.0 — Schema legend, large-scale campaign (2026-08-28)

- Schema legend: one colored chip per schema (name + table count) in the
  bottom-left corner, click to frame that schema's zone; hidden when the
  model has a single schema
- A clear hint when the input is MySQL or SQLite DDL instead of PostgreSQL
- Performance: pre-sorted BFS starts (layout of a 5000-table model drops
  from 894 ms to 56 ms), precompiled column regexes, tables built in one
  DocumentFragment and links redrawn in a single DOM write
- Large-scale harness (`tests/moissonner.py`, `tests/grand_banc.py`):
  hundreds of real-world schemas harvested from GitHub plus synthetic
  models up to 5000 tables, per-phase timings and DOM validation

### v0.5.0 — Draggable tables, test bench (2026-08-28)

- Tables can be dragged around the diagram, links redraw live; a table
  moved in the overview keeps its new home position
- Regression/benchmark runner (`tests/tester.py`) over the examples, the
  pgModeler sample models and an optional local corpus of big real-world
  schemas (GitLab: 1066 tables parsed in ~0.7 s), plus a pre-commit hook

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
