# Stage 1: pitch deck

The deliverable is `Parivaar_Cover_Team_Prometheus.pdf`. The organizers accept PDF, DOC or DOCX of **2 MB or less**, and the deck must include: Title, Problem Statement, Proposed Solution, Technology/Tech Stack, USP, Impact & Benefits, Business Model.

```bash
cd stage1_ppt/build
npm install        # first time only
npm run build      # build_deck.js -> ../Parivaar_Cover_Team_Prometheus.pptx
npm run pdf        # Keynote exports the .pptx to ../Parivaar_Cover_Team_Prometheus.pdf
npm run all        # both
```

How the pipeline fits together:
- `build_deck.js` generates the whole deck with pptxgenjs. It defines three layouts (`TITLE_DARK`, `CONTENT`, `CLOSING_DARK`), then composes each slide from small helpers (`card`, `text`, `iconCircle`, `avatar`). Icons are lucide icons from `react-icons`, rendered to PNG with `sharp`.
- Colors come from `THEME` and are always referenced as scheme colors (`C.text2`, `C.accent1`, ...). After `writeFile`, `apply_theme.js` (copied from the pptx skill) writes `THEME`'s colors into the deck's theme XML. Options that only accept hex (shadow color, for example) use `HEX` instead. A scheme color in a hex-only option makes `applyTheme` throw.
- The PDF is exported through Keynote (`export_pdf.applescript`) because LibreOffice isn't installed. That's also why every font is Arial: it renders identically in Keynote and PowerPoint. The first export may trigger a macOS prompt asking to allow Terminal to control Keynote.
- `slide_content.md` mirrors every slide's text and lists the sources behind each statistic. **The text lives in two places**: when you change wording, edit both `build_deck.js` and `slide_content.md`.

To check a build: run the pptx skill's `scripts/office/validate.py` on the .pptx, then render the PDF pages to images and look at every slide. Text overflow is the usual defect.

## Deck rules

- Keep decks short and pitch-like: one point per slide, few words, everything tied to the multi-generation family problem.
- Slide 4 must keep saying its premiums are **illustrative**.
- Every statistic needs a source listed in `slide_content.md`. Assumptions (the year 1 revenue math, the ~10 minute target) stay labeled as assumptions or targets.
- No accent bars or stripes. The repeated motif is family-member avatars with initials in circles and icons in sky circles.
