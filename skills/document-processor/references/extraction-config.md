# Extraction Configuration

## Supported File Formats

| Extension | Method | Library | Notes |
|-----------|--------|---------|-------|
| `.pdf` | native_pdf + ocr fallback | pymupdf (fitz) + pytesseract | OCR triggered when page has <50 chars but contains images |
| `.xlsx` / `.xls` | xlsx | openpyxl | One "page" per sheet, rendered as markdown table |
| `.pptx` / `.ppt` | pptx | python-pptx | One "page" per slide, includes speaker notes |
| `.csv` | text | built-in | Read as plain text |
| `.txt` / `.md` | text | built-in | Read as plain text |
| `.json` | text | built-in | Read as plain text |
| `.doc` / `.docx` | text | built-in | Limited — plain text only, no formatting |
| `.zip` | zip | built-in zipfile | Recursively extracts and processes contents |

## Unsupported (flagged for manual review)

- `.url` — URL shortcuts (delegate to data-puller for Chrome scraping)
- `.jpg` / `.png` — Images (would need vision model, not yet implemented)
- `.msg` — Outlook message files
- `.eml` — Email files

## Dependencies

```bash
# Core extraction
pip install pymupdf openpyxl python-pptx

# OCR (optional — only needed for scanned PDFs)
pip install pytesseract Pillow
brew install tesseract  # macOS system dependency

# LLM processing
pip install anthropic
```

## OCR Configuration

- **Threshold**: Pages with <50 characters after native extraction trigger OCR
- **Resolution**: 300 DPI rendering for OCR (good balance of quality vs speed)
- **Confidence**: pytesseract provides per-word confidence scores, averaged per page
- **Quality field**: `extraction_quality` in document_pages (1.0 = native, 0.3-0.9 = OCR)

## Spreadsheet Handling

- Each sheet becomes one "page" in document_pages
- Data rendered as markdown table (header row + separator + data rows)
- Rows capped at 500 per sheet to avoid massive text blobs
- Sheet name stored in metadata JSON

## ZIP Handling

- Extracted to temp directory, contents processed recursively
- Virtual file paths: `{zip_name}/{relative_path_inside_zip}`
- Temp directory cleaned up after processing
- Nested ZIPs are supported (recursive)

## Cost Estimates

Based on document complexity and the RLM processing approach:

| Document Type | Typical Pages | Est. Cost | Notes |
|--------------|---------------|-----------|-------|
| SAFE agreement | 2-5 | $0.01-0.03 | Simple extraction |
| Financial model (XLSX) | 3-10 sheets | $0.05-0.15 | Multiple extraction tasks |
| Pitch deck (PPTX) | 15-30 slides | $0.05-0.10 | Light content per slide |
| Legal contract | 10-50 pages | $0.10-0.30 | Dense text, multiple tasks |
| Full dataroom (20 files) | 50-200 pages | $0.50-2.00 | All predefined tasks |
| Large document (350 pages) | 350 | ~$0.60 | RLM recursive decomposition |
