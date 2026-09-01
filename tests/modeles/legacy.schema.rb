# Pre-2012 Rails db/schema.rb using the old hashrocket option syntax
# (:id => false, :force => true). The join table must NOT get a phantom
# id primary key. Kept tiny; the parser is exercised on real 16-year
# histories separately.
ActiveRecord::Schema.define(:version => 20110527000000) do

  create_table "users", :force => true do |t|
    t.string   "login"
    t.datetime "created_at"
  end

  create_table "tags", :force => true do |t|
    t.string "name"
  end

  create_table "taggings", :id => false, :force => true do |t|
    t.integer "tag_id"
    t.integer "user_id"
  end

end
