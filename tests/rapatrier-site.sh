#!/bin/sh
# Pull the failure store from mcdview.dev into tests/corpus/site-failures/ so the
# harness (grand_banc.py, test_invariants.py) can replay uploads that the hosted
# service flagged via `mcdview --diagnose`. Gitignored, like the rest of the
# corpus (uploaded schemas are private, shared only under the site's opt-in).
#
# Contract (frozen with mcdview-site): an authenticated HTTPS store, dir-per-id.
#   GET  {base}/failures                     -> index JSON [{id,input,ext,status,...}]
#   GET  {base}/failures/<id>/diagnose.json  -> the --diagnose output
#   GET  {base}/failures/<id>/<input>        -> the stored file (name = index "input")
#   DELETE {base}/failures/<id>              -> after a successful pull (idempotent)
#
# Env:
#   MCDVIEW_FAILURES_URL    base URL, e.g. https://mcdview.dev
#   MCDVIEW_FAILURES_TOKEN  bearer token (k8s secret, never committed)
set -u

base=${MCDVIEW_FAILURES_URL:-}
token=${MCDVIEW_FAILURES_TOKEN:-}
if [ -z "$base" ] || [ -z "$token" ]; then
    echo "set MCDVIEW_FAILURES_URL and MCDVIEW_FAILURES_TOKEN" >&2
    exit 2
fi
base=${base%/}
dest=$(dirname "$0")/corpus/site-failures
mkdir -p "$dest"
auth="Authorization: Bearer $token"

index=$(curl -sfL -H "$auth" "$base/failures") || {
    echo "cannot fetch $base/failures (token? service up?)" >&2; exit 1; }

# one "id<TAB>input-filename" per line from the index JSON. The filename comes
# from the index "input" field verbatim (e.g. input.sql) and is both the URL
# path segment and the local name, keeping the extension the harness replays by
echo "$index" | python3 -c '
import json, sys
for e in json.load(sys.stdin):
    print(e["id"], e.get("input") or ("input" + (e.get("ext") or "")), sep="\t")
' | while IFS='	' read -r id fname; do
    [ -n "$id" ] && [ -n "$fname" ] || continue
    d="$dest/$id"
    mkdir -p "$d"
    ok=1
    curl -sfL -H "$auth" -o "$d/diagnose.json" "$base/failures/$id/diagnose.json" || ok=0
    curl -sfL -H "$auth" -o "$d/$fname"        "$base/failures/$id/$fname"        || ok=0
    if [ "$ok" = 1 ]; then
        # both files pulled: delete server-side so the pull stays idempotent
        curl -sfL -X DELETE -H "$auth" "$base/failures/$id" >/dev/null \
            && echo "pulled $id ($fname)" \
            || echo "pulled $id but DELETE failed (will re-pull next time)"
    else
        echo "WARNING: incomplete pull for $id, left on server" >&2
        rm -rf "$d"
    fi
done

n=$(find "$dest" -mindepth 1 -maxdepth 1 -type d | wc -l)
echo "site-failures: $n failure(s) locally in $dest"
echo "replay them: ./tests/grand_banc.py  (they live under tests/corpus/)"
