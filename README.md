# PrinterHelper

PrinterHelper is a macOS helper app for manual duplex printing on printers that do not support automatic duplex.

It helps you:

- merge multiple files into one print batch
- convert mixed inputs to PDF
- generate two print-ready PDFs for manual duplex workflows
- preserve document boundaries between files
- optionally reorder files before generating the final print set

## What it supports

- PDF
- ZIP
- Word: `.doc` `.docx`
- PowerPoint: `.ppt` `.pptx`
- Images: `.png` `.jpg` `.jpeg` `.heic` `.tif` `.tiff` `.gif` `.bmp`
- Text: `.txt` `.rtf` `.rtfd`
- Pages / Keynote

## How it works

1. Launch `双面打印助手.app`
2. Upload files or a folder
3. Adjust file order if needed
4. Generate:
   - first-pass PDF
   - second-pass PDF
5. Print the first pass
6. Reinsert paper according to your printer's actual feed direction
7. Print the second pass PDF

The second-pass PDF is already prepared for manual duplex use:

- default output is not flipped by the tool itself
- page order is automatically reversed when needed
- blank pages are inserted automatically when needed

## Download

A ready-to-use macOS ZIP build is included in this repository:

- `downloads/PrinterHelper-macOS.zip`

After downloading:

1. Unzip the archive
2. Move `双面打印助手.app` into `/Applications`
3. If macOS shows a first-run warning, right-click the app and choose `Open`

## Repository layout

- `webapp/` local web UI and server
- `scripts/` conversion and packaging helpers
- `assets/` app icon source
- `downloads/` distributable ZIP package
- `docs/` sharing copy and documentation

## Notes

This repository intentionally contains only the PrinterHelper app assets, scripts, docs, and distributable package.
