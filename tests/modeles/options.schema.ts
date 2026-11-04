// Drizzle column options and table-level foreign keys (native parser).
import {
  pgTable, pgEnum, serial, varchar, timestamp, integer, numeric, text,
  doublePrecision, vector, foreignKey, primaryKey, index,
} from "drizzle-orm/pg-core";

export const roleEnum = pgEnum("user_role", ["admin", "member"]);

export const workspaces = pgTable("workspaces", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 120 }).notNull(),
  slug: varchar({ length: 32 }),
  createdAt: timestamp("created_at", { withTimezone: true, mode: "date" }).defaultNow().notNull(),
  updatedAt: timestamp("updated_at", { precision: 3, withTimezone: true }),
  budget: numeric("budget", { precision: 10, scale: 2 }),
  score: doublePrecision("score"),
  embedding: vector("embedding", { dimensions: 1536 }),
});

export const groups = pgTable("groups", {
  workspaceId: integer("workspace_id").notNull()
    .references(() => workspaces.id, { onDelete: "cascade", onUpdate: "set null" }),
  id: integer("id").notNull(),
  label: text("label"),
}, (t) => [primaryKey({ columns: [t.workspaceId, t.id] })]);

export const members = pgTable("members", {
  id: serial("id").primaryKey(),
  workspaceId: integer("workspace_id").notNull(),
  groupId: integer("group_id").notNull(),
  mentorId: integer("mentor_id"),
  role: roleEnum("role").default("member"),
}, (table) => [
  foreignKey({
    name: "members_group_fk",
    columns: [table.workspaceId, table.groupId],
    foreignColumns: [groups.workspaceId, groups.id],
  }).onDelete("restrict"),
  foreignKey({ columns: [table.mentorId], foreignColumns: [table.id] }),
  index("members_group_idx").on(table.workspaceId, table.groupId),
]);
