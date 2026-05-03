#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from manual_duplex_pdf import build_passes_from_paths

PDF_EXTS = {".pdf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff", ".gif", ".bmp"}
PAGES_EXTS = {".doc", ".docx", ".pages", ".txt", ".rtf", ".rtfd"}
KEYNOTE_EXTS = {".ppt", ".pptx", ".key"}
ARCHIVE_EXTS = {".zip"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def reveal_in_finder(path: Path) -> None:
    subprocess.Popen(
        ["/usr/bin/open", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def export_with_pages(source: Path, target: Path) -> None:
    script = f"""
set inFile to POSIX file "{source}"
set outFile to POSIX file "{target}"
tell application "Pages"
  activate
  set theDoc to open inFile
  export theDoc to outFile as PDF
  close theDoc saving no
end tell
"""
    subprocess.run(["osascript", "-"], input=script, text=True, check=True)


def export_with_keynote(source: Path, target: Path) -> None:
    script = f"""
set inFile to POSIX file "{source}"
set outFile to POSIX file "{target}"
tell application "Keynote"
  activate
  set theDoc to open inFile
  export theDoc to outFile as PDF
  close theDoc saving no
end tell
"""
    subprocess.run(["osascript", "-"], input=script, text=True, check=True)


def convert_one(source: Path, target: Path) -> None:
    suffix = source.suffix.lower()
    if suffix in PDF_EXTS:
        shutil.copy2(source, target)
        return
    if suffix in IMAGE_EXTS:
        run(["sips", "-s", "format", "pdf", str(source), "--out", str(target)])
        return
    if suffix in PAGES_EXTS:
        export_with_pages(source, target)
        return
    if suffix in KEYNOTE_EXTS:
        export_with_keynote(source, target)
        return
    raise ValueError(f"unsupported file type: {source.name}")


def extract_zip(source: Path, target_dir: Path) -> list[Path]:
    extract_dir = target_dir / source.stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    run(["ditto", "-x", "-k", str(source), str(extract_dir)])
    return collect_supported_files([extract_dir], target_dir)


def collect_supported_files(input_paths: list[Path], work_dir: Path) -> list[Path]:
    discovered: list[Path] = []

    for input_path in input_paths:
        if input_path.is_dir():
            children = sorted(path for path in input_path.rglob("*") if path.is_file())
        else:
            children = [input_path]

        for child in children:
            suffix = child.suffix.lower()
            if suffix in ARCHIVE_EXTS:
                discovered.extend(extract_zip(child, work_dir / "_expanded"))
            elif suffix in PDF_EXTS | IMAGE_EXTS | PAGES_EXTS | KEYNOTE_EXTS:
                discovered.append(child)

    return discovered


def convert_all(sources: list[Path], pdf_dir: Path) -> list[Path]:
    converted: list[Path] = []
    for index, source in enumerate(sources, start=1):
        safe_name = f"{index:03d}-{source.stem}.pdf"
        target = pdf_dir / safe_name
        convert_one(source, target)
        converted.append(target)
    return converted


def prepare_manual_duplex_bundle(
    input_paths: list[Path],
    output_dir: Path,
    prefix: str,
) -> dict[str, object]:
    pdf_dir = output_dir / "converted-pdfs"
    duplex_dir = output_dir / "manual-duplex"
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    duplex_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mixed-to-pdf-") as temp_dir:
        work_dir = Path(temp_dir)
        sources = collect_supported_files(input_paths, work_dir)

        if not sources:
            raise ValueError("No supported files found.")

        converted = convert_all(sources, pdf_dir)
        merged_path, odd_path, even_path, total_pages = build_passes_from_paths(
            converted, duplex_dir, prefix, keep_document_boundaries=True
        )

    return {
        "sources": sources,
        "converted": converted,
        "merged_path": merged_path,
        "odd_path": odd_path,
        "even_path": even_path,
        "total_pages": total_pages,
        "pdf_dir": pdf_dir,
        "duplex_dir": duplex_dir,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert mixed files/folders to PDF and prepare manual duplex printing PDFs."
    )
    parser.add_argument("paths", nargs="+", help="input files or folders")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="mixed-print-output",
        help="directory for converted PDFs and print-ready output",
    )
    parser.add_argument(
        "--prefix",
        default="print-batch",
        help="filename prefix for merged and duplex PDFs",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    input_paths = [Path(value).expanduser().resolve() for value in args.paths]
    missing = [path for path in input_paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"Input path not found: {path}", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        result = prepare_manual_duplex_bundle(input_paths, output_dir, args.prefix)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    converted = result["converted"]
    merged_path = result["merged_path"]
    odd_path = result["odd_path"]
    even_path = result["even_path"]
    total_pages = result["total_pages"]

    print(f"Converted {len(converted)} file(s) to PDF:")
    for path in converted:
        print(f"  {path}")
    print()
    print(f"Merged source PDF: {merged_path}")
    print(f"First pass PDF:    {odd_path}")
    print(f"Second pass PDF:   {even_path}")
    print(f"Total pages:       {total_pages}")

    reveal_in_finder(output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
