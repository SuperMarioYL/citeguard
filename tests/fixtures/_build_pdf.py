"""Generate the tiny `sample_paper.pdf` fixture used by the test suite.

The PDF is a hand-rolled minimal document with a single page of text containing
three identifiers (one real-looking arXiv ID, one DOI, one CVE).  We rebuild
it here rather than shipping an opaque binary so it stays auditable.

Run with::

    python tests/fixtures/_build_pdf.py
"""

from __future__ import annotations

from pathlib import Path


def build_pdf() -> bytes:
    # Page content stream — what pypdf will eventually read as text.
    content = (
        b"BT\n"
        b"/F1 10 Tf\n"
        b"72 720 Td\n"
        b"(References:) Tj\n"
        b"0 -20 Td\n"
        b"(See arXiv:2401.12345 for the method described.) Tj\n"
        b"0 -20 Td\n"
        b"(Following doi:10.1145/3460120.3484797 we adapt the protocol.) Tj\n"
        b"0 -20 Td\n"
        b"(The CVE-2024-99999 advisory documents the original flaw.) Tj\n"
        b"ET\n"
    )

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
    ]

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body_parts: list[bytes] = [header]
    offsets: list[int] = []
    cursor = len(header)
    for i, obj in enumerate(objects, start=1):
        offsets.append(cursor)
        chunk = f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        body_parts.append(chunk)
        cursor += len(chunk)

    xref_offset = cursor
    xref_lines = [b"xref\n", f"0 {len(objects) + 1}\n".encode(), b"0000000000 65535 f \n"]
    xref_lines.extend(f"{off:010d} 00000 n \n".encode() for off in offsets)
    body_parts.extend(xref_lines)

    trailer = (
        b"trailer\n"
        + f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode()
        + b"startxref\n"
        + f"{xref_offset}\n".encode()
        + b"%%EOF\n"
    )
    body_parts.append(trailer)
    return b"".join(body_parts)


def main() -> None:
    out = Path(__file__).parent / "sample_paper.pdf"
    out.write_bytes(build_pdf())
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
