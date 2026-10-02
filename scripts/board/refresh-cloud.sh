#!/usr/bin/env bash
# Lander Board refresh for a CLOUD Watchdog session, where `gh api graphql` answers 403, the
# branch-protection endpoint answers 403, and `gh --paginate` follows numeric-ID Link URLs the
# proxy refuses. gqlshim.py answers all three from REST; collect.py itself runs unmodified.
#
# The board scripts are extracted from origin/main on EVERY run (LANDER-BOARD.md section 9b), so
# a stale clone cannot render an old board. Only the shim and this driver run from the tree.
# Stops at the first failure, so a half-rebuilt board is never published. Publishing stays with
# the session: republish $OUT/board.html to the existing "Lander Board" artifact.
#
#   scripts/board/refresh-cloud.sh <out-dir>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
K="$(git -C "$HERE" rev-parse --show-toplevel)"
OUT="${1:?usage: refresh-cloud.sh <out-dir>}"
mkdir -p "$OUT/src"
git -C "$K" fetch -q origin main
for f in collect.py series.py build.py template.html seatstate.py; do
  git -C "$K" show "origin/main:scripts/board/$f" > "$OUT/src/$f"
done
echo "board scripts at korus origin/main $(git -C "$K" rev-parse --short origin/main)"
export LANDER_BOARD_OUT="$OUT"
python3 "$HERE/gqlshim.py" "$OUT/src"
python3 "$OUT/src/series.py"
python3 "$OUT/src/build.py"
# Disclose the collection path inside the page's own footer.
python3 - "$OUT/board.html" <<'PY'
import sys
p = sys.argv[1]
h = open(p, encoding="utf-8").read()
note = ('<br>Collected from a cloud Watchdog session: GraphQL is refused there, so the open-PR '
        'rollup, mergeability and required contexts are read from REST, and merge-queue entries '
        'are derived from each open pull request\'s timeline (added and removed events). Queue '
        'position is enqueue order; the per-entry state is not available over REST and shows as '
        'QUEUED.')
assert h.count("</foot>") == 1, "footer marker not found exactly once"
open(p, "w", encoding="utf-8").write(h.replace("</foot>", note + "\n  </foot>"))
PY
echo "--- $OUT/board.html ready ---"
