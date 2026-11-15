#!/bin/bash
# Render previews and PDF with headless Edge (Windows paths)
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
D="C:/Users/tonta/forClaudeCode/nasa-space-apps-2026/deliverable/slides"
for n in 1 2 3 4 5 6 7; do
  "$EDGE" --headless=new --disable-gpu --hide-scrollbars --window-size=1920,1080 --screenshot="$D/preview/slide$n.png" "file:///$D/slides.html?s=$n" >/dev/null 2>&1
done
"$EDGE" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$D/windfall-rice-slides.pdf" "file:///$D/slides.html" >/dev/null 2>&1
