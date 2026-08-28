# Rails db/schema.rb fixture (native parser, no external tool).
ActiveRecord::Schema[7.1].define(version: 2024_01_01_000000) do
  create_table "clients", force: :cascade do |t|
    t.string "nom", null: false
    t.string "courriel"
    t.datetime "created_at", null: false
  end

  create_table "commandes", force: :cascade do |t|
    t.bigint "client_id", null: false
    t.decimal "total", precision: 10, scale: 2
    t.datetime "created_at", null: false
  end

  create_table "lignes", force: :cascade do |t|
    t.bigint "commande_id", null: false
    t.string "produit"
    t.integer "quantite"
  end

  add_foreign_key "commandes", "clients"
  add_foreign_key "lignes", "commandes"
end
