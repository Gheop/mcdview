#!/bin/sh
# Fetch a local test corpus of big real-world PostgreSQL schemas into
# tests/corpus/ (gitignored — sizes and licenses vary, we only test on them).
# Each failure is a warning, not a stop: the runner tests what is there.
set -u
ici=$(dirname "$0")/corpus
mkdir -p "$ici"

prendre() {
    nom=$1; url=$2
    if [ -s "$ici/$nom" ]; then echo "déjà là : $nom"; return; fi
    echo "télécharge $nom"
    curl -sfL -o "$ici/$nom" "$url" || { echo "AVERTISSEMENT: échec $nom"; rm -f "$ici/$nom"; }
}

# Rails-generated structure.sql: hundreds of tables, good stress/benchmark
prendre gitlab.sql "https://gitlab.com/gitlab-org/gitlab/-/raw/master/db/structure.sql"
prendre discourse.sql "https://raw.githubusercontent.com/discourse/discourse/main/db/structure.sql"

ls -l "$ici"
