// Drizzle schema with the index forms of the table's third argument: array and
// object callbacks, index / uniqueIndex / unique, .on and .onOnly, a column-level
// .unique(), a composite primaryKey, and a column whose name comes from its field
// (no string argument) next to an onDelete string. Every FK is covered.
import { pgTable, uuid, text, integer, index, uniqueIndex, unique, primaryKey } from "drizzle-orm/pg-core";

export const teams = pgTable("teams", {
  id: uuid("id").primaryKey(),
  slug: text("slug").notNull().unique(),
});

export const clusters = pgTable(
  "clusters",
  {
    id: uuid("id").primaryKey(),
    team_id: uuid().notNull().references(() => teams.id, { onDelete: "cascade" }),
    ownerId: uuid("owner_id").references(() => teams.id),
  },
  (table) => [
    index("clusters_team_id_idx").on(table.team_id),
    uniqueIndex("clusters_owner_idx").onOnly(table.ownerId),
  ]
);

export const members = pgTable(
  "members",
  {
    clusterId: uuid("cluster_id").notNull().references(() => clusters.id),
    teamId: uuid("team_id").notNull().references(() => teams.id),
    rank: integer("rank"),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.clusterId, t.rank] }),
    teamIdx: index("members_team_idx").on(t.teamId),
    uq: unique().on(t.teamId, t.rank),
  })
);
