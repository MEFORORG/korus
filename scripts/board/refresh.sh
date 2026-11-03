#!/usr/bin/env bash
# Lander Board refresh. Collect -> derive -> render. Then republish board.html
# to the SAME artifact URL from the session that owns it.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
# Output goes beside the scripts unless LANDER_BOARD_OUT names elsewhere.
# LANDER_BOARD_ENGINE names an engine checkout; its held_pr_turns.py runs first so the board can
# split held pull requests from ready ones (LANDER-BOARD.md section 4).
if [ -n "${LANDER_BOARD_ENGINE:-}" ]; then
  export LANDER_BOARD_TURNS="${LANDER_BOARD_OUT:-$HERE}/turns.json"
  python "$LANDER_BOARD_ENGINE/scripts/coord/held_pr_turns.py" --json > "$LANDER_BOARD_TURNS"
fi
python "$HERE/collect.py"
python "$HERE/series.py"
python "$HERE/build.py"
echo "--- board.html ready in ${LANDER_BOARD_OUT:-$HERE} ---"
