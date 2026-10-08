"""Command-line access to catalog generation and matching."""
import argparse
import json
import sys
from pathlib import Path

from .catalog import build_catalog, write_catalog
from .engine import MatchingEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _parser():
    parser = argparse.ArgumentParser(description="Match fields to the LM model catalog")
    parser.add_argument("--catalog", type=Path, default=PROJECT_ROOT / "data" / "catalog.json")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build a portable catalog from existing LM exports")
    build.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "sources.json")
    build.add_argument("--source-root", type=Path)
    build.add_argument("--audit-flags", type=Path)
    build.add_argument("--supplementary", type=Path)
    build.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "catalog.json")
    build.add_argument("--templates-root", type=Path)
    commands.add_parser("summary", help="Show data provenance and validation statistics")
    match = commands.add_parser("match", help="Match the entire selected field set")
    match.add_argument("--fields", nargs="*", default=[])
    match.add_argument("--request-id")
    pair = commands.add_parser("pair", help="Check whether two fields share any model")
    pair.add_argument("left")
    pair.add_argument("right")
    field = commands.add_parser("field", help="Show a field and its compatible neighbors")
    field.add_argument("field_id")
    model = commands.add_parser("model", help="Show a model field set and its diagram IDs")
    model.add_argument("model_id")
    model_field = commands.add_parser("model-field", help="Show a published MF model-field")
    model_field.add_argument("model_id")
    diagram = commands.add_parser("diagram", aliases=["model-diagram"],
                                  help="Show a published T model-diagram's line assignments")
    diagram.add_argument("diagram_id")
    attachment = commands.add_parser("attachment", help="Attach an exact model-diagram to its topology")
    attachment.add_argument("diagram_id")
    attachment.add_argument("--svg", type=Path)
    attachment.add_argument("--stage", choices=["topology", "diagram", "attachment"],
                            default="attachment")
    topology = commands.add_parser("topology", help="Show a field-independent topology")
    topology.add_argument("topology_id")
    serve = commands.add_parser("serve", help="Serve the local clickable attachment preview")
    serve.add_argument("--port", type=int, default=8765)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            config = (json.loads(args.config.read_text(encoding="utf-8-sig"))
                      if args.config.is_file() else {})
            source_root = args.source_root or config.get("source_root")
            if not source_root:
                raise ValueError("Supply --source-root or config/sources.json")
            # A different export root must not inherit unrelated reference files.
            use_config_references = args.source_root is None
            audit = args.audit_flags or (config.get("audit_flags") if use_config_references else None)
            supplementary = args.supplementary or (
                config.get("supplementary") if use_config_references else None)
            catalog = build_catalog(source_root, audit_flags=audit, supplementary=supplementary)
            templates_root = args.templates_root or (
                config.get("templates_root") if use_config_references else None)
            attachment_validation = None
            if templates_root:
                from .attachments import AttachmentSystem
                from .topology import build_topology_catalog, write_topology_catalog
                registry = build_topology_catalog(templates_root, catalog, source_root)
                attachment_validation = AttachmentSystem(catalog, registry).validate_all()
                write_topology_catalog(registry, args.output.parent / "topologies.json")
            write_catalog(catalog, args.output)
            result = {"output": str(args.output.resolve()), "catalog_id": catalog["catalog_id"],
                      **catalog["metadata"]["statistics"],
                      "reference_validation": catalog["metadata"]["reference_validation"],
                      "attachment_validation": attachment_validation}
        else:
            engine = MatchingEngine.from_file(args.catalog)
            if args.command == "summary":
                result = engine.summary()
            elif args.command == "match":
                result = engine.match(args.fields, request_id=args.request_id)
            elif args.command == "pair":
                result = engine.field_compatibility(args.left, args.right)
            elif args.command == "field":
                result = engine.field_neighbors(args.field_id)
            elif args.command == "model":
                result = engine.model(args.model_id)
            elif args.command == "model-field":
                result = engine.model_field(args.model_id)
            elif args.command == "attachment":
                result = engine.attachment(args.diagram_id)
                if args.svg:
                    from .render import render_svg
                    args.svg.parent.mkdir(parents=True, exist_ok=True)
                    args.svg.write_text(render_svg(result, args.stage), encoding="utf-8")
                    result = {"output": str(args.svg.resolve()), "model_diagram_id": args.diagram_id,
                              "pipeline": result["pipeline"], "stage": args.stage}
            elif args.command == "topology":
                result = engine.topology(args.topology_id)
            elif args.command == "serve":
                from .server import serve
                serve(engine, port=args.port)
                return 0
            else:
                result = engine.diagram(args.diagram_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 2
