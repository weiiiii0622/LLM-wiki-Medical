#!/usr/bin/env python3

import argparse
from pathlib import Path

import pypdfium2 as pdfium


def split_pdf(input_pdf: str, start_page: int, end_page: int, output_pdf: str | None = None):
    input_path = Path(input_pdf)

    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    if input_path.suffix.lower() != ".pdf":
        raise ValueError("Input file must be a PDF")

    pdf = pdfium.PdfDocument(str(input_path))
    total_pages = len(pdf)

    if start_page < 1:
        raise ValueError("start_page must be >= 1")

    if end_page < start_page:
        raise ValueError("end_page must be >= start_page")

    if end_page > total_pages:
        raise ValueError(
            f"end_page exceeds total pages. PDF has {total_pages} pages."
        )

    if output_pdf is None:
        output_pdf = input_path.with_name(
            f"{input_path.stem}_pages_{start_page}_to_{end_page}.pdf"
        )

    output_path = Path(output_pdf)

    # pypdfium2 uses 0-based page indexes internally.
    page_indexes = list(range(start_page - 1, end_page))

    new_pdf = pdfium.PdfDocument.new()
    new_pdf.import_pages(pdf, page_indexes)
    new_pdf.save(str(output_path))

    pdf.close()
    new_pdf.close()

    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Split a PDF by start page and end page using pypdfium2."
    )

    parser.add_argument(
        "input_pdf",
        help="Path to the input PDF file",
    )

    parser.add_argument(
        "start_page",
        type=int,
        help="Start page, 1-based and inclusive",
    )

    parser.add_argument(
        "end_page",
        type=int,
        help="End page, 1-based and inclusive",
    )

    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to the output PDF file",
    )

    args = parser.parse_args()

    split_pdf(
        input_pdf=args.input_pdf,
        start_page=args.start_page,
        end_page=args.end_page,
        output_pdf=args.output,
    )


if __name__ == "__main__":
    main()