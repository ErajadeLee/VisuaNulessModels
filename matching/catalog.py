"""Normalize LM field/diagram exports into a checked, portable catalog."""
import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from .wolfram import parse_wolfram_literal

SCHEMA_VERSION = 2
SM_FIELDS = {
    "H": ((0, 0), (1,), Fraction(1, 2), "S"),
    "Q_L": ((1, 0), (1,), Fraction(1, 6), "F"),
    "u_R": ((1, 0), (0,), Fraction(2, 3), "F"),
    "d_R": ((1, 0), (0,), Fraction(-1, 3), "F"),
    "ell_L": ((0, 0), (1,), Fraction(-1, 2), "F"),
    "e_R": ((0, 0), (0,), Fraction(-1), "F"),
}
SM_ALIASES = {"q_L": "Q_L", "l_L": "ell_L", "ell_L": "ell_L"}


class CatalogError(ValueError):
    pass


def fieldset_key(field_ids):
    return ",".join(str(i) for i in sorted(set(field_ids)))


def model_id_for(field_ids):
    return "FS-" + "-".join(str(i) for i in sorted(set(field_ids)))


def natural_key(value):
    return tuple(int(part) if part.isdigit() else part
                 for part in re.split(r"(\d+)", value))


def _require(condition, message):
    if not condition:
        raise CatalogError(message)


def _read(path, role, manifest):
    path = Path(path).resolve()
    raw = path.read_bytes()
    manifest.append({"role": role, "path": str(path),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    return raw.decode("utf-8-sig")


def _field_records(rows):
    _require(isinstance(rows, list) and rows, "Field export must be a nonempty list")
    result = []
    seen = set()
    for field_id, row in enumerate(rows, 1):
        _require(isinstance(row, list) and len(row) == 4,
                 "Invalid field row {}".format(field_id))
        quantum, statistics, source_tag, multiplicity = row
        _require(isinstance(quantum, list) and len(quantum) == 3,
                 "Invalid quantum numbers for field {}".format(field_id))
        su3, su2, hypercharge = quantum
        _require(isinstance(su3, list) and len(su3) == 2 and
                 all(type(i) is int and i >= 0 for i in su3), "Invalid SU(3) labels")
        _require(isinstance(su2, list) and len(su2) == 1 and
                 type(su2[0]) is int and su2[0] >= 0, "Invalid SU(2) label")
        _require(isinstance(hypercharge, (int, Fraction)), "Hypercharge must be exact")
        _require(statistics in ("F", "S"), "Field statistics must be F or S")
        _require(isinstance(source_tag, str) and type(multiplicity) is int and
                 multiplicity > 0, "Invalid additional field metadata")
        y = Fraction(hypercharge)
        identity = (tuple(su3), tuple(su2), y, statistics)
        _require(identity not in seen, "Duplicate field quantum numbers and statistics")
        seen.add(identity)
        p, q = su3
        su3_dimension = (p + 1) * (q + 1) * (p + q + 2) // 2
        su2_dimension = su2[0] + 1
        sm_matches = []
        for name, (sm3, sm2, sm_y, sm_statistics) in SM_FIELDS.items():
            if statistics != sm_statistics:
                continue
            for conjugated in (False, True):
                target3 = sm3[::-1] if conjugated else sm3
                target_y = -sm_y if conjugated else sm_y
                if (tuple(su3), tuple(su2), y) == (target3, sm2, target_y):
                    sm_matches.append({"symbol": name, "conjugated": conjugated})
        result.append({
            "id": field_id,
            "su3": {"dynkin": su3, "dimension": su3_dimension},
            "su2": {"dynkin": su2, "dimension": su2_dimension},
            "hypercharge": {"numerator": y.numerator, "denominator": y.denominator,
                            "text": str(y)},
            "statistics": statistics,
            # Retain source metadata without guessing its physical interpretation.
            "source_tag": source_tag, "source_multiplicity": multiplicity,
            "label": "{}: {} ({},{},{})".format(
                field_id, statistics, su3_dimension, su2_dimension, y),
            "sm_quantum_matches": sm_matches,
        })
    return result


def _line(token, slot, fields):
    raw = token.strip().strip("$").strip()
    conjugated = raw.endswith(("^*", "^C"))
    base = raw[:-2] if conjugated else raw
    if base.isdigit():
        field_id = int(base)
        _require(field_id in fields, "Unknown field {} at {}".format(field_id, slot))
        statistics = fields[field_id]["statistics"]
        return {"slot": slot, "kind": "bsm", "field_id": field_id,
                "sm_symbol": None, "statistics": statistics,
                "conjugated": conjugated,
                "conjugation": ("charge" if statistics == "F" else "complex")
                               if conjugated else None,
                "raw_label": raw}
    name = base.lstrip("\\")
    name = SM_ALIASES.get(name, name)
    _require(name in SM_FIELDS, "Unknown SM token {!r} at {}".format(raw, slot))
    statistics = SM_FIELDS[name][3]
    _require(not (name == "H" and raw.endswith("^C")), "H^C is not a supported SM label")
    return {"slot": slot, "kind": "sm", "field_id": None,
            "sm_symbol": name, "statistics": statistics,
            "conjugated": conjugated,
            "conjugation": ("charge" if statistics == "F" else "complex")
                           if conjugated else None,
            "raw_label": raw}


def _diagram_records(source_root, fields, manifest):
    directory = source_root / "TopoAssignedOutInLines" / "formatm"
    paths = sorted(directory.glob("T*-*.m"), key=lambda path: natural_key(path.stem))
    _require(paths, "No diagram exports found in {}".format(directory))
    field_lookup = {field["id"]: field for field in fields}
    result, seen = [], set()
    for path in paths:
        _require(re.fullmatch(r"T\d+-\d+", path.stem), "Invalid template filename")
        rows = parse_wolfram_literal(_read(path, "diagram-export", manifest))
        _require(isinstance(rows, list) and rows, "Empty diagram export: " + str(path))
        internal_count = None
        for row in rows:
            _require(isinstance(row, str), "Diagram rows must be strings")
            # The remaining suffix is TeX row formatting, not field data.
            body = row.split(r"\\", 1)[0].strip()
            columns = [part.strip().strip("$") for part in body.split("&")]
            _require(len(columns) in (13, 14), "Expected 8 external and 4/5 internal lines")
            diagram_id = columns[0]
            _require(re.fullmatch(re.escape(path.stem) + r"-[1-9]\d*", diagram_id),
                     "Diagram ID does not match template: " + diagram_id)
            _require(diagram_id not in seen, "Duplicate diagram: " + diagram_id)
            seen.add(diagram_id)
            externals = [_line(token, "E{}".format(i), field_lookup)
                         for i, token in enumerate(columns[1:9], 1)]
            internals = [_line(token, "I{}".format(i), field_lookup)
                         for i, token in enumerate(columns[9:], 1)]
            _require(all(line["kind"] == "sm" for line in externals),
                     "External lines must be SM fields: " + diagram_id)
            if internal_count is None:
                internal_count = len(internals)
            _require(internal_count == len(internals), "Inconsistent template line count")
            field_ids = sorted({line["field_id"] for line in internals
                                if line["kind"] == "bsm"})
            _require(field_ids, "Diagram contains no BSM fields: " + diagram_id)
            result.append({"id": diagram_id, "template_id": path.stem,
                           "model_id": model_id_for(field_ids),
                           "external_lines": externals, "internal_lines": internals})
    return sorted(result, key=lambda record: natural_key(record["id"]))


def _proper_subsets(field_ids):
    for size in range(len(field_ids)):
        yield from itertools.combinations(field_ids, size)


def _models(diagrams):
    groups = defaultdict(list)
    for diagram in diagrams:
        field_ids = tuple(sorted({line["field_id"] for line in diagram["internal_lines"]
                                  if line["kind"] == "bsm"}))
        groups[field_ids].append(diagram["id"])
    all_sets = set(groups)
    result = []
    for field_ids in sorted(groups, key=lambda key: (len(key), key)):
        diagram_ids = groups[field_ids]
        minimal = not any(subset in all_sets for subset in _proper_subsets(field_ids))
        result.append({"id": model_id_for(field_ids), "internal_id": model_id_for(field_ids),
                       "field_ids": list(field_ids), "minimal": minimal,
                       "model_field_id": None, "reference_id": None,
                       "diagram_ids": diagram_ids, "diagram_count": len(diagram_ids),
                       "representative_diagram_id": diagram_ids[0]})
    return result


def _check_references(fields, models, diagrams, audit_path, supplementary_path, manifest):
    # At this stage model IDs are still internal FS keys. Assign public IDs after
    # the source field sets and every published diagram have been cross-checked.
    model_lookup = {model["id"]: model for model in models}
    validation = {"audit_flag_rows": 0, "published_model_diagram_rows": 0,
                  "published_minimal_model_rows": 0, "corrected_original_flags": None}
    if audit_path:
        rows = json.loads(_read(audit_path, "minimality-audit", manifest))
        _require(isinstance(rows, list), "Audit flags must be a list")
        audit = {}
        for row in rows:
            name = row["name"]
            _require(name not in audit, "Duplicate audit diagram: " + name)
            _require(row["strictFlag"] in (r"\ding{51}", r"\ding{55}"),
                     "Unknown strict minimality flag")
            audit[name] = row
        _require(set(audit) == {diagram["id"] for diagram in diagrams},
                 "Audit and source diagram IDs differ")
        changed = 0
        for diagram in diagrams:
            expected = model_lookup[diagram["model_id"]]["minimal"]
            row = audit[diagram["id"]]
            _require((row["strictFlag"] == r"\ding{51}") == expected,
                     "Strict minimality mismatch: " + diagram["id"])
            changed += row["originalFlag"] != row["strictFlag"]
        validation["audit_flag_rows"] = len(audit)
        validation["corrected_original_flags"] = changed
    if supplementary_path:
        document = _read(supplementary_path, "supplementary-reference", manifest)
        field_lookup = {field["id"]: field for field in fields}
        diagram_lookup = {diagram["id"]: diagram for diagram in diagrams}
        published_diagrams = set()
        for line in document.splitlines():
            line = line.strip()
            if not re.match(r"^T\d+-\d+-\d+&", line):
                continue
            columns = line.split(r"\\", 1)[0].split("&")
            diagram_id = columns[0]
            _require(diagram_id not in published_diagrams,
                     "Duplicate published model-diagram: " + diagram_id)
            _require(diagram_id in diagram_lookup,
                     "Unknown published model-diagram: " + diagram_id)
            published_diagrams.add(diagram_id)
            diagram = diagram_lookup[diagram_id]
            expected_lines = diagram["external_lines"] + diagram["internal_lines"]
            _require(len(columns) == len(expected_lines) + 2,
                     "Published line count mismatch: " + diagram_id)
            expected_minimal = model_lookup[diagram["model_id"]]["minimal"]
            _require(columns[1] in (r"\ding{51}", r"\ding{55}") and
                     (columns[1] == r"\ding{51}") == expected_minimal,
                     "Published diagram minimality mismatch: " + diagram_id)
            for token, expected_line in zip(columns[2:], expected_lines):
                published_line = _line(token, expected_line["slot"], field_lookup)
                # q_L/Q_L and fermion ^*/^C are equivalent source conventions.
                for key in expected_line:
                    if key != "raw_label":
                        _require(published_line[key] == expected_line[key],
                                 "Published line assignment mismatch: {} {}".format(
                                     diagram_id, expected_line["slot"]))
        _require(published_diagrams == set(diagram_lookup),
                 "Published and source model-diagram IDs differ")
        validation["published_model_diagram_rows"] = len(published_diagrams)

        published, reference_ids = set(), set()
        for line in document.splitlines():
            line = line.strip()
            if not re.match(r"^MF-[345]i-\d+&", line):
                continue
            columns = line.split("&")
            _require(len(columns) == 3, "Invalid published minimal-model row")
            reference_id = columns[0]
            _require(reference_id not in reference_ids, "Duplicate published model ID")
            reference_ids.add(reference_id)
            field_ids = tuple(int(value) for value in re.findall(r"\d+", columns[1]))
            _require(field_ids == tuple(sorted(set(field_ids))), "Invalid published field set")
            _require(int(reference_id.split("-")[1][0]) == len(field_ids),
                     "Published model field count mismatch")
            internal_id = model_id_for(field_ids)
            _require(internal_id in model_lookup and model_lookup[internal_id]["minimal"],
                     "Published minimality mismatch: " + reference_id)
            _require(internal_id not in published, "Duplicate published field set")
            published.add(internal_id)
            diagram_ids = re.findall(r"T\d+-\d+-\d+", columns[2])
            _require(set(diagram_ids) == set(model_lookup[internal_id]["diagram_ids"]) and
                     len(diagram_ids) == len(set(diagram_ids)),
                     "Published diagram list mismatch: " + reference_id)
            model_lookup[internal_id]["reference_id"] = reference_id
        _require(published == {model["id"] for model in models if model["minimal"]},
                 "Published and computed minimal model sets differ")
        validation["published_minimal_model_rows"] = len(published)
    return validation


def _assign_published_ids(models, diagrams):
    canonical_ids = {}
    field_ids = {}
    for model in models:
        model["model_field_id"] = model["reference_id"]
        model["id"] = model["model_field_id"] or model["internal_id"]
        canonical_ids[model["internal_id"]] = model["id"]
        field_ids[model["internal_id"]] = model["model_field_id"]
    for diagram in diagrams:
        internal_id = diagram["model_id"]
        diagram["model_diagram_id"] = diagram["id"]
        diagram["model_internal_id"] = internal_id
        diagram["model_field_id"] = field_ids[internal_id]
        diagram["model_id"] = canonical_ids[internal_id]


def make_indexes(fields, models):
    by_field = {str(field["id"]): [] for field in fields}
    by_fieldset = {}
    for model in models:
        by_fieldset[fieldset_key(model["field_ids"])] = model["id"]
        for field_id in model["field_ids"]:
            by_field[str(field_id)].append(model["id"])
    aliases = {}
    for model in models:
        aliases[model["internal_id"]] = model["id"]
        aliases[model["id"]] = model["id"]
    return {"field_to_models": by_field, "fieldset_to_model": by_fieldset,
            "model_aliases": aliases}


def statistics_for(fields, models, diagrams):
    minimal = {model["id"] for model in models if model["minimal"]}
    return {
        "field_count": len(fields), "model_count": len(models),
        "minimal_model_count": len(minimal), "diagram_count": len(diagrams),
        "minimal_diagram_count": sum(diagram["model_id"] in minimal for diagram in diagrams),
        "template_count": len({diagram["template_id"] for diagram in diagrams}),
        "models_by_field_count": dict(sorted(Counter(
            str(len(model["field_ids"])) for model in models).items())),
    }


def catalog_id_for(catalog):
    payload = {name: catalog[name] for name in
               ("schema_version", "fields", "models", "diagrams", "indexes")}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_catalog(catalog):
    """Check the portable catalog before exposing matching results."""
    _require(catalog.get("schema_version") == SCHEMA_VERSION, "Unsupported catalog schema")
    fields, models, diagrams = (catalog[name] for name in ("fields", "models", "diagrams"))
    _require(fields and models and diagrams, "Catalog must not be empty")
    field_lookup = {field["id"]: field for field in fields}
    model_lookup = {model["id"]: model for model in models}
    diagram_lookup = {diagram["id"]: diagram for diagram in diagrams}
    _require(len(field_lookup) == len(fields) and
             all(type(field_id) is int and field_id > 0 for field_id in field_lookup),
             "Invalid or duplicate field IDs")
    _require(len(model_lookup) == len(models), "Duplicate model IDs")
    _require(len(diagram_lookup) == len(diagrams), "Duplicate diagram IDs")
    all_sets = {tuple(model["field_ids"]) for model in models}
    reference_ids = [model["reference_id"] for model in models if model["reference_id"]]
    _require(len(reference_ids) == len(set(reference_ids)), "Duplicate reference model IDs")
    assigned = []
    for model in models:
        ids = model["field_ids"]
        _require(ids and ids == sorted(set(ids)) and set(ids) <= set(field_lookup),
                 "Invalid model field IDs")
        _require(model["internal_id"] == model_id_for(ids), "Invalid internal field-set key")
        published_id = model["model_field_id"]
        _require(model["reference_id"] == published_id, "Inconsistent published ID")
        _require(model["id"] == (published_id or model["internal_id"]),
                 "Model does not use its published ID")
        if published_id:
            match = re.fullmatch(r"MF-([345])i-([1-9]\d*)", published_id)
            _require(match is not None and int(match.group(1)) == len(ids),
                     "Invalid published model-field ID")
        expected_minimal = not any(subset in all_sets for subset in _proper_subsets(ids))
        _require(type(model["minimal"]) is bool and model["minimal"] == expected_minimal,
                 "Incorrect minimality: " + model["id"])
        _require(not model["reference_id"] or model["minimal"],
                 "A published minimal model cannot be non-minimal")
        diagram_ids = model["diagram_ids"]
        _require(diagram_ids and len(diagram_ids) == len(set(diagram_ids)) and
                 all(diagram_id in diagram_lookup for diagram_id in diagram_ids),
                 "Invalid model diagram references")
        _require(model["diagram_count"] == len(diagram_ids) and
                 model["representative_diagram_id"] in diagram_ids,
                 "Incorrect diagram count or representative")
        _require(all(diagram_lookup[diagram_id]["model_id"] == model["id"]
                     for diagram_id in diagram_ids), "Diagram ownership mismatch")
        assigned.extend(diagram_ids)
    _require(Counter(assigned) == Counter(diagram_lookup.keys()),
             "Each diagram must belong to exactly one model")
    for diagram in diagrams:
        _require(re.fullmatch(re.escape(diagram["template_id"]) + r"-[1-9]\d*",
                              diagram["id"]), "Invalid diagram/template ID")
        internal = diagram["internal_lines"]
        external = diagram["external_lines"]
        _require(len(external) == 8 and len(internal) in (4, 5), "Invalid line count")
        for prefix, lines in (("E", external), ("I", internal)):
            for number, line in enumerate(lines, 1):
                _require(line["slot"] == "{}{}".format(prefix, number), "Invalid line slot")
                expected = _line(line["raw_label"], line["slot"], field_lookup)
                _require(line == expected, "Line assignment metadata mismatch")
        _require(all(line["kind"] == "sm" for line in external), "Non-SM external field")
        field_ids = sorted({line["field_id"] for line in internal if line["kind"] == "bsm"})
        _require(diagram["model_internal_id"] == model_id_for(field_ids),
                 "Diagram field set mismatch")
        owner = model_lookup[diagram["model_id"]]
        _require(diagram["model_diagram_id"] == diagram["id"] and
                 diagram["model_internal_id"] == owner["internal_id"] and
                 diagram["model_field_id"] == owner["model_field_id"],
                 "Diagram/model published numbering mismatch")
    _require(catalog["indexes"] == make_indexes(fields, models), "Inconsistent matching indexes")
    _require(catalog["metadata"]["statistics"] == statistics_for(fields, models, diagrams),
             "Inconsistent catalog statistics")
    _require(catalog["catalog_id"] == catalog_id_for(catalog), "Catalog content hash mismatch")


def build_catalog(source_root, audit_flags=None, supplementary=None):
    source_root = Path(source_root).resolve()
    manifest = []
    fields = _field_records(parse_wolfram_literal(
        _read(source_root / "allnewfield.m", "field-export", manifest)))
    diagrams = _diagram_records(source_root, fields, manifest)
    models = _models(diagrams)
    reference_validation = _check_references(
        fields, models, diagrams, audit_flags, supplementary, manifest)
    _assign_published_ids(models, diagrams)
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "model_definition": "distinct-new-field-set",
            "minimality_definition": "no-catalog-model-has-a-proper-subset-of-new-fields",
            "model_numbering": "published-MF-ID-when-present-otherwise-internal-FS-key",
            "model_diagram_numbering": "source-T-ID-checked-against-supplementary",
            "statistics": statistics_for(fields, models, diagrams),
            "source_files": manifest,
            "reference_validation": reference_validation,
        },
        "fields": fields, "models": models, "diagrams": diagrams,
        "indexes": make_indexes(fields, models),
    }
    catalog["catalog_id"] = catalog_id_for(catalog)
    validate_catalog(catalog)
    return catalog


def write_catalog(catalog, output):
    validate_catalog(catalog)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after the complete JSON has been written successfully.
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def load_catalog(path):
    catalog = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    validate_catalog(catalog)
    return catalog
