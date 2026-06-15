from __future__ import annotations

import html
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .parser import default_invoice_dir, default_json_dir, list_invoices, parse_invoice


class OcrBrowserServer:
    def __init__(self, root: Path, host: str, port: int) -> None:
        self.root = root.resolve()
        self.invoice_dir = default_invoice_dir(self.root).resolve()
        self.json_dir = default_json_dir(self.root).resolve()
        self.host = host
        self.port = port

    def serve_forever(self) -> None:
        parent = self

        class Handler(OcrBrowserHandler):
            server_config = parent

        httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        print(f"SLAIF OCR browser: http://{self.host}:{self.port}/")
        print(f"Invoices: {self.invoice_dir}")
        print(f"JSON: {self.json_dir}")
        httpd.serve_forever()


class OcrBrowserHandler(BaseHTTPRequestHandler):
    server_config: OcrBrowserServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self._send_html(render_index(self.server_config))
        if path == "/api/invoices":
            return self._send_json(invoice_index(self.server_config))
        if path == "/api/parse":
            params = parse_qs(parsed.query)
            name = params.get("file", [""])[0]
            return self._parse_one(name)
        if path == "/api/parse-all":
            return self._parse_all()
        if path.startswith("/pdf/"):
            return self._serve_pdf(path.removeprefix("/pdf/"))
        if path.startswith("/json/"):
            return self._serve_json_file(path.removeprefix("/json/"))

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _parse_one(self, raw_name: str) -> None:
        pdf_path = safe_child(self.server_config.invoice_dir, raw_name, suffix=".pdf")
        if pdf_path is None:
            return self.send_error(HTTPStatus.BAD_REQUEST, "Invalid PDF name")
        if not pdf_path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "PDF not found")
        result = parse_invoice(pdf_path, root=self.server_config.root, write_json=True, out_dir=self.server_config.json_dir)
        self._send_json(result)

    def _parse_all(self) -> None:
        results = [
            parse_invoice(pdf, root=self.server_config.root, write_json=True, out_dir=self.server_config.json_dir)
            for pdf in list_invoices(self.server_config.invoice_dir)
        ]
        self._send_json({"count": len(results), "results": results})

    def _serve_pdf(self, raw_name: str) -> None:
        pdf_path = safe_child(self.server_config.invoice_dir, raw_name, suffix=".pdf")
        if pdf_path is None or not pdf_path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "PDF not found")
        data = pdf_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'inline; filename="{pdf_path.name}"')
        self.end_headers()
        self.wfile.write(data)

    def _serve_json_file(self, raw_name: str) -> None:
        json_path = safe_child(self.server_config.json_dir, raw_name, suffix=".json")
        if json_path is None or not json_path.exists():
            return self.send_error(HTTPStatus.NOT_FOUND, "JSON not found")
        self._send_bytes(json_path.read_bytes(), "application/json; charset=utf-8")

    def _send_html(self, body: str) -> None:
        self._send_bytes(body.encode("utf-8"), "text/html; charset=utf-8")

    def _send_json(self, payload: object) -> None:
        self._send_bytes(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8")

    def _send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def safe_child(parent: Path, raw_name: str, suffix: str) -> Path | None:
    name = unquote(raw_name)
    if not name or Path(name).name != name or not name.lower().endswith(suffix):
        return None
    return (parent / name).resolve()


def invoice_index(config: OcrBrowserServer) -> list[dict[str, object]]:
    rows = []
    config.json_dir.mkdir(parents=True, exist_ok=True)
    for pdf in list_invoices(config.invoice_dir):
        json_path = config.json_dir / f"{pdf.stem}.json"
        rows.append(
            {
                "name": pdf.name,
                "size": pdf.stat().st_size,
                "pdf_url": f"/pdf/{quote(pdf.name)}",
                "json_url": f"/json/{quote(json_path.name)}" if json_path.exists() else None,
                "parsed": json_path.exists(),
            }
        )
    return rows


def render_index(config: OcrBrowserServer) -> str:
    rows = invoice_index(config)
    buttons = "\n".join(
        f"""
        <button class="invoice" data-name="{html.escape(str(row['name']))}" data-pdf="{html.escape(str(row['pdf_url']))}" data-json="{html.escape(str(row['json_url'] or ''))}">
          <span>{html.escape(str(row['name']))}</span>
          <small>{'parsed' if row['parsed'] else 'not parsed'}</small>
        </button>
        """
        for row in rows
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SLAIF OCR Invoice Browser</title>
  <style>
    :root {{
      --ink: #17211b;
      --muted: #65736a;
      --paper: #fbf7ef;
      --panel: #fffdf8;
      --line: #d9d0c2;
      --accent: #0e6b5f;
      --warn: #9b4a16;
    }}
    body {{
      margin: 0;
      font-family: ui-serif, Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(14,107,95,.16), transparent 34rem),
        linear-gradient(135deg, #fbf7ef, #efe6d8);
    }}
    header {{
      padding: 1.1rem 1.5rem;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 253, 248, .82);
      backdrop-filter: blur(8px);
    }}
    h1 {{ margin: 0; font-size: 1.35rem; letter-spacing: .02em; }}
    main {{
      display: grid;
      grid-template-columns: minmax(230px, 320px) minmax(0, 1fr) minmax(280px, 420px);
      gap: 1rem;
      height: calc(100vh - 71px);
      padding: 1rem;
      box-sizing: border-box;
    }}
    aside, section {{
      background: rgba(255, 253, 248, .88);
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      box-shadow: 0 18px 55px rgba(62, 48, 32, .12);
    }}
    .list {{ overflow: auto; padding: .65rem; }}
    .invoice {{
      width: 100%;
      display: flex;
      justify-content: space-between;
      gap: .7rem;
      padding: .68rem .75rem;
      margin-bottom: .45rem;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fffaf1;
      color: var(--ink);
      cursor: pointer;
      text-align: left;
    }}
    .invoice:hover, .invoice.active {{ border-color: var(--accent); box-shadow: inset 4px 0 0 var(--accent); }}
    .invoice small {{ color: var(--muted); white-space: nowrap; }}
    .toolbar {{
      display: flex;
      gap: .5rem;
      align-items: center;
      padding: .7rem;
      border-bottom: 1px solid var(--line);
    }}
    .toolbar button {{
      border: 0;
      border-radius: 999px;
      padding: .58rem .85rem;
      color: white;
      background: var(--accent);
      cursor: pointer;
    }}
    .toolbar button.secondary {{ background: #6d5d42; }}
    iframe {{ width: 100%; height: calc(100% - 56px); border: 0; background: white; }}
    pre {{
      margin: 0;
      padding: 1rem;
      overflow: auto;
      height: calc(100% - 56px);
      box-sizing: border-box;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: .82rem;
      background: #1d231f;
      color: #eaf1eb;
    }}
    .empty {{ padding: 1rem; color: var(--muted); }}
    @media (max-width: 980px) {{
      main {{ grid-template-columns: 1fr; height: auto; }}
      aside, section {{ min-height: 45vh; }}
      iframe, pre {{ height: 60vh; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>SLAIF OCR Invoice Browser</h1>
  </header>
  <main>
    <aside>
      <div class="toolbar">
        <button class="secondary" id="parseAll">Parse all</button>
      </div>
      <div class="list">{buttons or '<p class="empty">No PDFs found in data/invoice.</p>'}</div>
    </aside>
    <section>
      <div class="toolbar">
        <button id="parseOne" disabled>Parse selected</button>
        <span id="selectedName">No invoice selected</span>
      </div>
      <iframe id="preview" title="PDF preview"></iframe>
    </section>
    <section>
      <div class="toolbar">
        <button class="secondary" id="loadJson" disabled>Load JSON</button>
      </div>
      <pre id="json">Select an invoice.</pre>
    </section>
  </main>
  <script>
    let selected = null;
    const preview = document.getElementById('preview');
    const jsonPanel = document.getElementById('json');
    const selectedName = document.getElementById('selectedName');
    const parseOne = document.getElementById('parseOne');
    const loadJson = document.getElementById('loadJson');

    async function fetchJson(url) {{
      const response = await fetch(url);
      if (!response.ok) throw new Error(await response.text());
      return await response.json();
    }}

    document.querySelectorAll('.invoice').forEach(button => {{
      button.addEventListener('click', async () => {{
        document.querySelectorAll('.invoice').forEach(b => b.classList.remove('active'));
        button.classList.add('active');
        selected = {{
          name: button.dataset.name,
          pdf: button.dataset.pdf,
          json: button.dataset.json
        }};
        preview.src = selected.pdf;
        selectedName.textContent = selected.name;
        parseOne.disabled = false;
        loadJson.disabled = !selected.json;
        jsonPanel.textContent = selected.json ? 'JSON exists. Click Load JSON.' : 'No JSON yet. Click Parse selected.';
      }});
    }});

    parseOne.addEventListener('click', async () => {{
      if (!selected) return;
      jsonPanel.textContent = 'Parsing...';
      const data = await fetchJson('/api/parse?file=' + encodeURIComponent(selected.name));
      selected.json = '/json/' + encodeURIComponent(selected.name.replace(/\\.pdf$/i, '.json'));
      loadJson.disabled = false;
      jsonPanel.textContent = JSON.stringify(data, null, 2);
    }});

    loadJson.addEventListener('click', async () => {{
      if (!selected || !selected.json) return;
      const data = await fetchJson(selected.json);
      jsonPanel.textContent = JSON.stringify(data, null, 2);
    }});

    document.getElementById('parseAll').addEventListener('click', async () => {{
      jsonPanel.textContent = 'Parsing all invoices...';
      const data = await fetchJson('/api/parse-all');
      jsonPanel.textContent = JSON.stringify(data, null, 2);
    }});
  </script>
</body>
</html>"""
