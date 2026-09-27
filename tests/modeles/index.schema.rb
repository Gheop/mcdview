# Rails db/schema.rb with the index forms a dump can hold: t.index inside the
# block (array, %w[] and single-string columns) and add_index after the tables
# (pre-Rails-5, hashrocket options). Every foreign key is covered by an index.
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000000) do
  create_table "blobs", force: :cascade do |t|
    t.string "key", null: false
    t.index ["key"], name: "index_blobs_on_key", unique: true
  end

  create_table "attachments", force: :cascade do |t|
    t.string "record_type", null: false
    t.bigint "record_id", null: false
    t.bigint "blob_id", null: false
    t.index ["blob_id"], name: "index_attachments_on_blob_id"
    t.index %w[record_type record_id blob_id], name: "index_attachments_uniqueness", unique: true
  end

  create_table "variants", force: :cascade do |t|
    t.bigint "blob_id", null: false
    t.index "blob_id", name: "index_variants_on_blob_id", unique: true
  end

  create_table "comments", force: :cascade do |t|
    t.bigint "attachment_id"
  end

  add_index "comments", ["attachment_id"], :name => "index_comments_on_attachment_id"

  add_foreign_key "attachments", "blobs", column: "blob_id"
  add_foreign_key "variants", "blobs", column: "blob_id"
  add_foreign_key "comments", "attachments"
end
