from __future__ import annotations

import argparse
import json
from pathlib import Path

from .parser import batch_parse, default_invoice_dir, default_json_dir, default_root, list_invoices, parse_invoice
from .server import OcrBrowserServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="slaif-ocr", description="SLAIF invoice OCR CLI")
    parser.add_argument("--root", type=Path, default=default_root(), help="Project root directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available invoice PDFs")
    list_parser.add_argument("--invoice-dir", type=Path, default=None)

    parse_parser = subparsers.add_parser("parse", help="Parse one invoice PDF into ocr/json")
    parse_parser.add_argument("pdf", type=Path)
    parse_parser.add_argument("--out-dir", type=Path, default=None)
    parse_parser.add_argument("--stdout", action="store_true", help="Also print JSON to stdout")

    batch_parser = subparsers.add_parser("batch", help="Parse all invoice PDFs")
    batch_parser.add_argument("--invoice-dir", type=Path, default=None)
    batch_parser.add_argument("--out-dir", type=Path, default=None)

    serve_parser = subparsers.add_parser("serve", help="Run local PDF browser UI")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    root = args.root.resolve()

    if args.command == "list":
        invoice_dir = (args.invoice_dir or default_invoice_dir(root)).resolve()
        for pdf in list_invoices(invoice_dir):
            print(pdf)
        return

    if args.command == "parse":
        out_dir = (args.out_dir or default_json_dir(root)).resolve()
        result = parse_invoice(args.pdf, root=root, write_json=True, out_dir=out_dir)
        print(result["output_file"])
        if args.stdout:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.command == "batch":
        invoice_dir = (args.invoice_dir or default_invoice_dir(root)).resolve()
        out_dir = (args.out_dir or default_json_dir(root)).resolve()
        results = batch_parse(invoice_dir, root=root, out_dir=out_dir)
        print(json.dumps({"count": len(results), "out_dir": str(out_dir)}, ensure_ascii=False, indent=2))
        return

    if args.command == "serve":
        OcrBrowserServer(root=root, host=args.host, port=args.port).serve_forever()
        return

    raise SystemExit(f"Unsupported command: {args.command}")
