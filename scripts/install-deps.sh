#!/bin/bash
# VFT Fund Tools — Dependency Installer
set -e

echo "[VFT] Installing core dependencies..."
pip install pymupdf openpyxl python-pptx anthropic gspread google-auth

echo ""
echo "[VFT] Verifying imports..."
python -c "import fitz; import openpyxl; from pptx import Presentation; import anthropic; import gspread; print('[VFT] All core deps OK')"

echo ""
echo "[VFT] Optional: For OCR support on scanned PDFs, run:"
echo "  pip install pytesseract Pillow"
echo "  brew install tesseract"
