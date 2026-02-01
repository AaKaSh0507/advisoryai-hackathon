#!/bin/bash
# Run tests with coverage and generate text report
# Usage: ./scripts/run_tests.sh

set -e

cd "$(dirname "$0")/.."

echo "Running tests with coverage..."
python -m pytest tests/ "$@"

# Generate text coverage report
echo ""
echo "Generating text coverage report..."
python -m coverage report > coverage/test_coverage.txt

echo ""
echo "Coverage reports generated:"
echo "  - Text:  coverage/test_coverage.txt"
echo "  - HTML:  coverage/html/index.html"
echo ""
echo "Text coverage summary:"
cat coverage/test_coverage.txt
