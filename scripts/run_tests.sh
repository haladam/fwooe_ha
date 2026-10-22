#!/usr/bin/env bash
# Run the tests:  ./scripts/run_tests.sh
#
# * The feed model (parsing, filters, change detection) needs nothing but Python 3.12+.
# * The Home Assistant tests need `pip install -r requirements_test.txt` (Python 3.14 for current
#   Home Assistant releases); without it they are skipped here and CI runs them.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== feed model =="
python3 -B -m unittest tests.test_models

echo "== Home Assistant tests =="
if python3 -c 'import pytest_homeassistant_custom_component' 2>/dev/null; then
  python3 -m pytest -q
else
  echo "skipped: pytest-homeassistant-custom-component is not installed (CI runs these)"
fi
