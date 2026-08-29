# Example diagrams (Mermaid)

These are the committed example models rendered as [Mermaid](https://mermaid.js.org/)
`erDiagram` blocks — GitHub and GitLab render them natively below, right in this
page. Generated from the SQL with `mcdview.py <model> --to-mermaid`.

This is the static view. For the **interactive** explorer (click a table to
isolate it, zoom, search, drag), open the live demo:
<https://gheop.github.io/mcdview/>.

## Mediatheque

```mermaid
erDiagram
    editeur {
        integer idediteur PK
        character nom
        character ville
        integer _idmodificateur FK
        timestamp _datemodification
    }
    auteur {
        integer idauteur PK
        character nom
        character prenom
        smallint anneenaissance
        integer _idmodificateur FK
        timestamp _datemodification
    }
    genre {
        integer idgenre PK
        character libelle
    }
    ouvrage {
        integer idouvrage PK
        character titre
        character isbn
        smallint anneeparution
        integer idediteur FK
        integer idgenre FK
        text resume
        integer _idmodificateur FK
        timestamp _datemodification
    }
    ouvrage_auteur {
        integer idouvrage PK, FK
        integer idauteur PK, FK
        character role
    }
    exemplaire {
        integer idexemplaire PK
        integer idouvrage FK
        character codebarre
        character etat
        date dateachat
        integer idsite FK
        integer _idmodificateur FK
        timestamp _datemodification
    }
    site {
        integer idsite PK
        character nom
        text adresse
    }
    abonne {
        integer idabonne PK
        character nom
        character prenom
        character courriel
        date datenaissance
        integer idsite FK
        date dateinscription
        integer _idmodificateur FK
        timestamp _datemodification
    }
    agent {
        integer idagent PK
        character nom
        character prenom
        integer idsite FK
    }
    pret {
        integer idpret PK
        integer idexemplaire FK
        integer idabonne FK
        integer idagent FK
        date datepret
        date dateretourprevu
        date dateretour
        integer _idmodificateur FK
        timestamp _datemodification
    }
    reservation {
        integer idreservation PK
        integer idouvrage FK
        integer idabonne FK
        timestamp datereservation
        character etat
    }
    penalite {
        integer idpenalite PK
        integer idpret FK
        numeric montant
        character motif
        date datereglement
        integer _idmodificateur FK
        timestamp _datemodification
    }
    editeur ||--o{ ouvrage : ""
    genre ||--o{ ouvrage : ""
    ouvrage ||--o{ ouvrage_auteur : ""
    auteur ||--o{ ouvrage_auteur : ""
    ouvrage ||--o{ exemplaire : ""
    site ||--o{ exemplaire : ""
    site ||--o{ abonne : ""
    site ||--o{ agent : ""
    exemplaire ||--o{ pret : ""
    abonne ||--o{ pret : ""
    agent ||--o{ pret : ""
    ouvrage ||--o{ reservation : ""
    abonne ||--o{ reservation : ""
    pret ||--o{ penalite : ""
    agent ||--o{ editeur : ""
    agent ||--o{ auteur : ""
    agent ||--o{ ouvrage : ""
    agent ||--o{ exemplaire : ""
    agent ||--o{ abonne : ""
    agent ||--o{ penalite : ""
```

## Chinook

```mermaid
erDiagram
    album {
        INT album_id PK
        VARCHAR title
        INT artist_id FK
    }
    artist {
        INT artist_id PK
        VARCHAR name
    }
    customer {
        INT customer_id PK
        VARCHAR first_name
        VARCHAR last_name
        VARCHAR company
        VARCHAR address
        VARCHAR city
        VARCHAR state
        VARCHAR country
        VARCHAR postal_code
        VARCHAR phone
        VARCHAR fax
        VARCHAR email
        INT support_rep_id FK
    }
    employee {
        INT employee_id PK
        VARCHAR last_name
        VARCHAR first_name
        VARCHAR title
        INT reports_to FK
        TIMESTAMP birth_date
        TIMESTAMP hire_date
        VARCHAR address
        VARCHAR city
        VARCHAR state
        VARCHAR country
        VARCHAR postal_code
        VARCHAR phone
        VARCHAR fax
        VARCHAR email
    }
    genre {
        INT genre_id PK
        VARCHAR name
    }
    invoice {
        INT invoice_id PK
        INT customer_id FK
        TIMESTAMP invoice_date
        VARCHAR billing_address
        VARCHAR billing_city
        VARCHAR billing_state
        VARCHAR billing_country
        VARCHAR billing_postal_code
        NUMERIC total
    }
    invoice_line {
        INT invoice_line_id PK
        INT invoice_id FK
        INT track_id FK
        NUMERIC unit_price
        INT quantity
    }
    media_type {
        INT media_type_id PK
        VARCHAR name
    }
    playlist {
        INT playlist_id PK
        VARCHAR name
    }
    playlist_track {
        INT playlist_id PK, FK
        INT track_id PK, FK
    }
    track {
        INT track_id PK
        VARCHAR name
        INT album_id FK
        INT media_type_id FK
        INT genre_id FK
        VARCHAR composer
        INT milliseconds
        INT bytes
        NUMERIC unit_price
    }
    artist ||--o{ album : ""
    employee ||--o{ customer : ""
    employee ||--o{ employee : ""
    customer ||--o{ invoice : ""
    invoice ||--o{ invoice_line : ""
    track ||--o{ invoice_line : ""
    playlist ||--o{ playlist_track : ""
    track ||--o{ playlist_track : ""
    album ||--o{ track : ""
    genre ||--o{ track : ""
    media_type ||--o{ track : ""
```

## Northwind

```mermaid
erDiagram
    categories {
        smallint category_id PK
        character category_name
        text description
        bytea picture
    }
    customer_customer_demo {
        character customer_id PK, FK
        character customer_type_id PK, FK
    }
    customer_demographics {
        character customer_type_id PK
        text customer_desc
    }
    customers {
        character customer_id PK
        character company_name
        character contact_name
        character contact_title
        character address
        character city
        character region
        character postal_code
        character country
        character phone
        character fax
    }
    employees {
        smallint employee_id PK
        character last_name
        character first_name
        character title
        character title_of_courtesy
        date birth_date
        date hire_date
        character address
        character city
        character region
        character postal_code
        character country
        character home_phone
        character extension
        bytea photo
        text notes
        smallint reports_to FK
        character photo_path
    }
    employee_territories {
        smallint employee_id PK, FK
        character territory_id PK, FK
    }
    order_details {
        smallint order_id PK, FK
        smallint product_id PK, FK
        real unit_price
        smallint quantity
        real discount
    }
    orders {
        smallint order_id PK
        character customer_id FK
        smallint employee_id FK
        date order_date
        date required_date
        date shipped_date
        smallint ship_via FK
        real freight
        character ship_name
        character ship_address
        character ship_city
        character ship_region
        character ship_postal_code
        character ship_country
    }
    products {
        smallint product_id PK
        character product_name
        smallint supplier_id FK
        smallint category_id FK
        character quantity_per_unit
        real unit_price
        smallint units_in_stock
        smallint units_on_order
        smallint reorder_level
        integer discontinued
    }
    region {
        smallint region_id PK
        character region_description
    }
    shippers {
        smallint shipper_id PK
        character company_name
        character phone
    }
    suppliers {
        smallint supplier_id PK
        character company_name
        character contact_name
        character contact_title
        character address
        character city
        character region
        character postal_code
        character country
        character phone
        character fax
        text homepage
    }
    territories {
        character territory_id PK
        character territory_description
        smallint region_id FK
    }
    us_states {
        smallint state_id PK
        character state_name
        character state_abbr
        character state_region
    }
    customers ||--o{ orders : ""
    employees ||--o{ orders : ""
    shippers ||--o{ orders : ""
    products ||--o{ order_details : ""
    orders ||--o{ order_details : ""
    categories ||--o{ products : ""
    suppliers ||--o{ products : ""
    region ||--o{ territories : ""
    territories ||--o{ employee_territories : ""
    employees ||--o{ employee_territories : ""
    customer_demographics ||--o{ customer_customer_demo : ""
    customers ||--o{ customer_customer_demo : ""
    employees ||--o{ employees : ""
```

## Pagila

```mermaid
erDiagram
    customer {
        integer customer_id PK
        integer store_id FK
        text first_name
        text last_name
        text email
        integer address_id FK
        boolean activebool
        date create_date
        timestamp last_update
        integer active
        uuid uuid
    }
    actor {
        integer actor_id PK
        text first_name
        text last_name
        timestamp last_update
    }
    category {
        integer category_id PK
        text name
        timestamp last_update
    }
    film {
        integer film_id PK
        text title
        text description
        public release_year
        integer language_id FK
        integer original_language_id FK
        smallint rental_duration
        numeric rental_rate
        smallint length
        numeric replacement_cost
        public rating
        timestamp last_update
        text special_features
        tsvector fulltext
        numeric length_hours
    }
    film_actor {
        integer actor_id PK, FK
        integer film_id PK, FK
        timestamp last_update
    }
    film_category {
        integer film_id PK, FK
        integer category_id PK, FK
        timestamp last_update
    }
    film_embedding {
        integer film_id PK, FK
        public embedding
        timestamp last_update
    }
    address {
        integer address_id PK
        text address
        text address2
        text district
        integer city_id FK
        text postal_code
        text phone
        timestamp last_update
    }
    city {
        integer city_id PK
        text city
        integer country_id FK
        timestamp last_update
    }
    country {
        integer country_id PK
        text country
        timestamp last_update
    }
    inventory {
        integer inventory_id PK
        integer film_id FK
        integer store_id FK
        timestamp last_update
    }
    language {
        integer language_id PK
        text name
        timestamp last_update
    }
    payment {
        integer payment_id PK
        integer customer_id FK
        integer staff_id FK
        integer rental_id FK
        numeric amount
        timestamp payment_date PK
        uuid uuid
    }
    rental {
        integer rental_id PK
        timestamp rental_date
        integer inventory_id FK
        integer customer_id FK
        timestamp return_date
        integer staff_id FK
        timestamp last_update
        uuid uuid
    }
    staff {
        integer staff_id PK
        text first_name
        text last_name
        integer address_id FK
        text email
        integer store_id FK
        boolean active
        text username
        text password
        timestamp last_update
        bytea picture
    }
    store {
        integer store_id PK
        integer manager_staff_id
        integer address_id FK
        timestamp last_update
    }
    city ||--o{ address : ""
    country ||--o{ city : ""
    address ||--o{ customer : ""
    store ||--o{ customer : ""
    actor ||--o{ film_actor : ""
    film ||--o{ film_actor : ""
    category ||--o{ film_category : ""
    film ||--o{ film_category : ""
    film ||--o{ film_embedding : ""
    language ||--o{ film : ""
    film ||--o{ inventory : ""
    store ||--o{ inventory : ""
    customer ||--o{ payment : ""
    rental ||--o{ payment : ""
    staff ||--o{ payment : ""
    customer ||--o{ rental : ""
    inventory ||--o{ rental : ""
    staff ||--o{ rental : ""
    address ||--o{ staff : ""
    store ||--o{ staff : ""
    address ||--o{ store : ""
```

