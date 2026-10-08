"""Local model workbench and read-only matching/attachment API."""
import json
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .render import render_svg

PREVIEW_ROOT = Path(__file__).resolve().parents[1] / "preview"
STATIC_ROUTES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/attachment": ("attachment.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assets/i18n.js": ("i18n.js", "text/javascript; charset=utf-8"),
    "/assets/attachment.js": ("attachment.js", "text/javascript; charset=utf-8"),
    "/assets/app-icon.svg": ("app-icon.svg", "image/svg+xml"),
    "/favicon.ico": ("app-icon.ico", "image/x-icon"),
}


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, engine, **kwargs):
        self.engine = engine
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # The standard access log adds no useful data to the preview console.
        pass

    def _send(self, body, mime="application/json; charset=utf-8", status=200):
        if not isinstance(body, bytes):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value, status=200):
        self._send(json.dumps(value, ensure_ascii=False), status=status)

    def do_GET(self):
        parsed = urlsplit(self.path)
        route = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if route in STATIC_ROUTES:
                filename, mime = STATIC_ROUTES[route]
                self._send((PREVIEW_ROOT / filename).read_bytes(), mime)
            elif route == "/api/fields":
                self._json({"catalog_id": self.engine.catalog_id,
                            "statistics": self.engine.summary()["statistics"],
                            "fields": self.engine.fields()})
            elif route == "/api/match":
                raw = query.get("fields", [""])[0]
                fields = raw.split(",") if raw else []
                self._json(self.engine.match(fields, request_id=query.get("request_id", [None])[0]))
            elif route == "/api/models":
                raw = query.get("fields", [""])[0]
                fields = raw.split(",") if raw else []
                selected = self.engine.normalize_fields(fields)
                ids = self.engine.matching_models(selected, complete=True) if selected else []
                rows = [self.engine.model(identifier) for identifier in ids]
                self._json({"catalog_id": self.engine.catalog_id,
                            "selected_field_ids": list(selected),
                            "count": len(rows), "items": rows,
                            "diagram_count": sum(row["diagram_count"] for row in rows)})
            elif route.startswith("/api/models/"):
                self._json(self.engine.model(route[len("/api/models/"):]))
            elif route == "/api/health":
                self._json({"status": "ok", "catalog_id": self.engine.catalog_id,
                            **self.engine.validate_attachments()})
            elif route == "/api/diagrams":
                prefix = query.get("q", [""])[0]
                rows = [diagram for diagram in self.engine._catalog["diagrams"]
                        if prefix.lower() in diagram["id"].lower()]
                self._json({"total": len(rows), "items": [
                    {"id": row["id"], "model_field_id": row["model_field_id"]}
                    for row in rows[:24]]})
            elif route.startswith("/api/attachments/"):
                identifier = route[len("/api/attachments/"):]
                if identifier.endswith(".svg"):
                    identifier = identifier[:-4]
                    packet = self.engine.attachment(identifier)
                    svg = render_svg(packet, stage=query.get("stage", ["attachment"])[0])
                    self._send(svg, "image/svg+xml; charset=utf-8")
                else:
                    self._json(self.engine.attachment(identifier))
            elif route.startswith("/api/model-fields/"):
                self._json(self.engine.model_field(route[len("/api/model-fields/"):]))
            elif route.startswith("/api/topologies/"):
                self._json(self.engine.topology(route[len("/api/topologies/"):]))
            else:
                self._json({"error": "Unknown endpoint"}, 404)
        except (ValueError, KeyError) as exc:
            self._json({"error": str(exc)}, 400)
        except OSError as exc:
            self._json({"error": str(exc)}, 500)


def create_server(engine, port=8765, handler_class=Handler):
    engine.validate_attachments()
    return ThreadingHTTPServer(("127.0.0.1", port), partial(handler_class, engine=engine))


def serve(engine, port=8765):
    server = create_server(engine, port)
    print("Model workbench: http://127.0.0.1:{}".format(server.server_port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
