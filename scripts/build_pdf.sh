#!/usr/bin/env bash
# Render a markdown document in paper/ to PDF with pandoc and xelatex.
#
# The source's leading title block (H1, subtitle, byline, first horizontal rule)
# is stripped and re-supplied as document metadata, so the markdown keeps a
# readable heading while the PDF gets a proper title block instead of the same
# text appearing twice.
#
# Metadata is written to a temporary YAML file rather than passed with -M,
# because -M escapes its values and a LaTeX line break in the byline would
# render literally.
#
# Requires: pandoc, texlive-xetex, and the DejaVu fonts.
#   Debian/Ubuntu: apt install pandoc texlive-xetex fonts-dejavu
#   macOS:         brew install pandoc && brew install --cask mactex-no-gui
#
# Usage:
#   scripts/build_pdf.sh paper/DRIFT_SUMMARY.md
#   scripts/build_pdf.sh paper/DRIFT_SUMMARY.md out.pdf "Optional subtitle"
set -euo pipefail

SRC="${1:?usage: build_pdf.sh <input.md> [output.pdf] [subtitle]}"
OUT="${2:-${SRC%.md}.pdf}"
SUBTITLE="${3:-A Controlled Study of Forgetting Policies in LLM Agent Memory}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

command -v pandoc  >/dev/null || { echo "pandoc not found"; exit 1; }
command -v xelatex >/dev/null || { echo "xelatex not found"; exit 1; }

TITLE=$(grep -m1 '^# ' "$SRC" | sed 's/^# //')
META=$(mktemp /tmp/pandoc-meta-XXXX.yaml)
trap 'rm -f "$META"' EXIT

cat > "$META" <<YAML
---
title: "$TITLE"
subtitle: "$SUBTITLE"
author: "Nandan Hemanth and Hao Wang, Stevens Institute of Technology"
date: "$(date +'%B %Y')"
---
YAML

# Everything before the first horizontal rule is the source's own title block.
sed '1,/^---$/d' "$SRC" \
| pandoc "$META" - -f markdown -o "$OUT" \
    --pdf-engine=xelatex \
    --include-in-header="$ROOT/paper/assets/pandoc-header.tex" \
    -V geometry:"a4paper,margin=1.6cm" \
    -V mainfont="DejaVu Serif" \
    -V sansfont="DejaVu Sans" \
    -V monofont="DejaVu Sans Mono" \
    -V fontsize=9pt \
    -V colorlinks=true -V linkcolor=black -V urlcolor="[HTML]{1D7368}" \
    -V documentclass=article

echo "pdf -> $OUT ($(python3 -c "from pypdf import PdfReader;print(len(PdfReader('$OUT').pages))") pages)"
