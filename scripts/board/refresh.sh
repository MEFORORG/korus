#!/usr/bin/env bash
# Lander Board refresh. Collect -> derive -> render. Then republish board.html
# to the SAME artifact URL from the session that owns it.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
# Output goes beside the scripts unless LANDER_BOARD_OUT names elsewhere.
python "$HERE/collect.py"
python "$HERE/series.py"
python "$HERE/build.py"
echo "--- board.html ready in ${LANDER_BOARD_OUT:-$HERE} ---"
