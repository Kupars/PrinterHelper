#!/usr/bin/env python3
"""
Prepare two PDF passes for manual duplex printing on simplex printers.

Default mode matches the common HP LaserJet workflow where:
1. Print odd pages in ascending order.
2. Put the output stack back into the input tray without rotating it.
3. Print even pages in descending order.

If the source PDF has an odd number of pages, the second-pass PDF gets a
leading blank page so the unmatched last front page stays blank on the back.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from pypdf import PdfReader, PdfWriter


def add_blank_like(writer: PdfWriter, page) -> None:
    box = page.mediabox
    writer.add_blank_page(width=float(box.width), height=float(box.height))


def make_blank_like(page):
    writer = PdfWriter()
    add_blank_like(writer, page)
    return writer.pages[0]


def collect_pages(input_paths: list[Path], keep_document_boundaries: bool = False) -> list:
    pages = []

    for index, input_path in enumerate(input_paths):
        reader = PdfReader(str(input_path))
        if len(reader.pages) == 0:
            raise ValueError(f"input PDF has no pages: {input_path.name}")
        pages.extend(reader.pages)
        is_last_document = index == len(input_paths) - 1
        if keep_document_boundaries and not is_last_document and len(reader.pages) % 2 == 1:
            pages.append(make_blank_like(reader.pages[-1]))

    return pages


def write_merged_source(
    input_paths: list[Path],
    output_dir: Path,
    prefix: str,
    keep_document_boundaries: bool,
) -> Path:
    writer = PdfWriter()

    for page in collect_pages(input_paths, keep_document_boundaries=keep_document_boundaries):
        writer.add_page(page)

    merged_path = output_dir / f"{prefix}.merged-source.pdf"
    with merged_path.open("wb") as f:
        writer.write(f)

    return merged_path


def build_passes_from_paths(
    input_paths: list[Path],
    output_dir: Path,
    prefix: str,
    keep_document_boundaries: bool = True,
) -> tuple[Path, Path, Path, int]:
    pages = collect_pages(input_paths, keep_document_boundaries=keep_document_boundaries)
    total_pages = len(pages)

    if total_pages == 0:
        raise ValueError("input PDF has no pages")

    odd_writer = PdfWriter()
    even_writer = PdfWriter()

    odd_indices = list(range(0, total_pages, 2))
    even_indices = list(range(1, total_pages, 2))

    for index in odd_indices:
        odd_writer.add_page(pages[index])

    if total_pages % 2 == 1:
        add_blank_like(even_writer, pages[-1])

    for index in reversed(even_indices):
        even_writer.add_page(pages[index])

    output_dir.mkdir(parents=True, exist_ok=True)
    merged_path = write_merged_source(
        input_paths,
        output_dir,
        prefix,
        keep_document_boundaries=keep_document_boundaries,
    )
    odd_path = output_dir / f"{prefix}.pass1-odd-asc.pdf"
    even_path = output_dir / f"{prefix}.pass2-even-desc.pdf"

    with odd_path.open("wb") as f:
        odd_writer.write(f)

    with even_path.open("wb") as f:
        even_writer.write(f)

    return merged_path, odd_path, even_path, total_pages


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create two PDFs for manual duplex printing without page misalignment."
    )
    parser.add_argument("input_pdf", nargs="+", help="one or more source PDF files")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="manual-duplex-output",
        help="directory for the generated PDFs (default: %(default)s)",
    )
    parser.add_argument(
        "--prefix",
        help="output filename prefix (default: source filename without extension)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    input_paths = [Path(value).expanduser().resolve() for value in args.input_pdf]
    missing_paths = [path for path in input_paths if not path.is_file()]
    if missing_paths:
        for path in missing_paths:
            print(f"Input PDF not found: {path}", file=sys.stderr)
        return 1

    prefix = args.prefix or input_paths[0].stem
    output_dir = Path(args.output_dir).expanduser().resolve()

    try:
        merged_path, odd_path, even_path, total_pages = build_passes_from_paths(
            input_paths, output_dir, prefix
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to prepare manual duplex PDFs: {exc}", file=sys.stderr)
        return 1

    print(f"Created merged source PDF: {merged_path}")
    print(f"Created first pass PDF:  {odd_path}")
    print(f"Created second pass PDF: {even_path}")
    print()
    print("How to print:")
    print("1. Print the first-pass PDF with normal single-sided printing.")
    print("2. Take the whole output stack as-is; do not rotate or flip it.")
    print("3. Put the stack back into the input tray.")
    print("4. Print the second-pass PDF with normal single-sided printing.")

    if total_pages % 2 == 1:
        print("Note: a leading blank back page was inserted for the last odd page.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
