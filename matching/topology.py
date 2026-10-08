"""Extract fixed topology/slot templates from the existing TikZ-Feynman files."""
import copy
import hashlib
import itertools
import json
import math
import re
from collections import Counter
from pathlib import Path

from .catalog import CatalogError, natural_key

TOPOLOGY_SCHEMA_VERSION = 1
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"


class TopologyError(CatalogError):
    pass


def require(condition, message):
    if not condition:
        raise TopologyError(message)


def _coordinate(expression, coordinates):
    expression = re.sub(r"\s+", "", expression)
    absolute = re.fullmatch(r"\((" + NUMBER + r"),(" + NUMBER + r")\)", expression)
    if absolute:
        return [float(absolute.group(1)), float(absolute.group(2))]
    relative = re.fullmatch(r"\(\$\((\w+)\)\+\((.*?)\)\$\)", expression)
    require(relative is not None, "Unsupported TeX coordinate: " + expression)
    base, offset = relative.groups()
    require(base in coordinates, "Unknown coordinate base: " + base)
    cartesian = re.fullmatch(r"(" + NUMBER + r"),(" + NUMBER + r")", offset)
    polar = re.fullmatch(r"(" + NUMBER + r"):(" + NUMBER + r")", offset)
    require(cartesian is not None or polar is not None, "Unsupported offset: " + offset)
    if cartesian:
        dx, dy = map(float, cartesian.groups())
    else:
        angle, radius = map(float, polar.groups())
        dx = radius * math.cos(math.radians(angle))
        dy = radius * math.sin(math.radians(angle))
    return [round(coordinates[base][0] + dx, 10),
            round(coordinates[base][1] + dy, 10)]


def _slot(text, kind):
    matches = re.findall(r"\$" + kind + r"_?\{?([1-9]\d*)\}?\$", text)
    require(len(matches) == 1, "Expected one {} label: {}".format(kind, text))
    return kind + matches[0]


def _edge_id(topology_id, source, target):
    return "{}:{}:{}".format(topology_id, *sorted((source, target)))


def parse_tex_template(text, template_id):
    require(re.fullmatch(r"T[1-9]\d*-[1-9]\d*", template_id), "Invalid template ID")
    topology_id = template_id.split("-")[0]
    # Comments are ignored; TeX commands are never executed.
    text = re.sub(r"(?<!\\)%[^\n]*", "", text)
    coordinates, definitions, external_labels = {}, [], {}
    vertex_pattern = re.compile(
        r"\\vertex(?:\[[^\]]*\])?\s+at\s*(\(\$.*?\$\)|\([^()]*\))"
        r"\s*\((\w+)\)\s*(?:\{(.*?)\})?\s*;", re.S)
    for match in vertex_pattern.finditer(text):
        expression, name, content = match.groups()
        point = _coordinate(expression, coordinates)
        definitions.append((name, point))
        # Some original files reuse a label-node name. E labels are keyed by
        # their printed slot, not by those auxiliary TeX node names.
        coordinates[name] = point
        if content and re.search(r"\$E_?\{?\d", content):
            slot = _slot(content, "E")
            require(slot not in external_labels, "Duplicate external label: " + slot)
            external_labels[slot] = point
    body = re.search(r"\\diagram\*\s*\{(.*?)\}\s*;", text, re.S)
    require(body is not None, "Missing diagram body: " + template_id)
    # Lookahead retains the middle node of a chain a--b--c.
    edge_pattern = re.compile(r"(?=\((\w+)\)\s*--\s*\[([^\]]*)\]\s*\((\w+)\))")
    raw_edges = edge_pattern.findall(body.group(1))
    require(raw_edges, "No edges: " + template_id)
    degree = Counter()
    used_pairs = set()
    for source, _, target in raw_edges:
        require(source in coordinates and target in coordinates, "Unknown edge endpoint")
        require(source != target, "Self-loop in tree topology")
        pair = tuple(sorted((source, target)))
        require(pair not in used_pairs, "Duplicate edge in topology")
        used_pairs.add(pair)
        degree[source] += 1
        degree[target] += 1
    nodes = sorted(degree)
    physical_definitions = Counter(name for name, _ in definitions if name in degree)
    require(all(physical_definitions[name] == 1 for name in nodes),
            "Physical vertices must have unique TeX definitions")
    leaves = [name for name in nodes if degree[name] == 1]
    require(len(leaves) == 8, "Expected eight external endpoints: " + template_id)
    require(set(external_labels) == {"E" + str(i) for i in range(1, 9)},
            "Expected E1..E8 labels")
    leaf_slots = {}
    for slot, point in external_labels.items():
        distances = sorted((math.dist(point, coordinates[name]), name) for name in leaves)
        require(distances[0][0] <= 0.85 and distances[1][0] - distances[0][0] > 0.1,
                "Ambiguous external slot position: " + slot)
        leaf = distances[0][1]
        require(leaf not in leaf_slots, "Two E labels refer to one external endpoint")
        leaf_slots[leaf] = slot
    vertices = [{"id": name, "kind": "external" if degree[name] == 1 else "interaction",
                 "x": coordinates[name][0], "y": coordinates[name][1]}
                for name in nodes]
    topology_edges, lines = [], []
    for source, style, target in raw_edges:
        options = [option.strip() for option in style.split(",")]
        require(any(option in ("fermion", "anti fermion", "scalar",
                               "charged scalar", "anti charged scalar") for option in options),
                "Unknown line style: " + style)
        is_external = source in leaf_slots or target in leaf_slots
        kind = "external" if is_external else "internal"
        slot = leaf_slots[source if source in leaf_slots else target] if is_external else _slot(style, "I")
        statistics = "F" if any("fermion" in option for option in options) else "S"
        reverse = any(option.startswith("anti ") for option in options)
        has_arrow = any(option in ("fermion", "anti fermion", "charged scalar",
                                   "anti charged scalar") for option in options)
        arrow = {"source": target if reverse else source,
                 "target": source if reverse else target} if has_arrow else None
        if is_external:
            label = external_labels[slot]
        else:
            ax, ay = coordinates[source]
            bx, by = coordinates[target]
            length = math.hypot(bx - ax, by - ay)
            side = -1 if re.search(r"edge\s+label\s*'", style) else 1
            label = [(ax + bx) / 2 - side * (by - ay) / length * 0.24,
                     (ay + by) / 2 + side * (bx - ax) / length * 0.24]
        edge_id = _edge_id(topology_id, source, target)
        topology_edges.append({"id": edge_id, "kind": kind,
                               "endpoints": sorted((source, target))})
        lines.append({"slot": slot, "edge_id": edge_id, "kind": kind,
                      "source": source, "target": target, "statistics": statistics,
                      "line_type": "fermion" if statistics == "F" else "scalar",
                      "stroke_pattern": "solid" if statistics == "F" else "dashed",
                      "arrow": arrow, "label_position": label, "source_style": style})
    internal_count = len(raw_edges) - 8
    require(internal_count in (4, 5), "Expected four or five internal edges")
    require({line["slot"] for line in lines} ==
            {"E" + str(i) for i in range(1, 9)} |
            {"I" + str(i) for i in range(1, internal_count + 1)}, "Missing/duplicate line slot")
    topology = {"id": topology_id,
                "vertices": [{"id": vertex["id"], "kind": vertex["kind"]} for vertex in vertices],
                "edges": sorted(topology_edges, key=lambda edge: edge["id"])}
    template = {"id": template_id, "topology_id": topology_id, "vertices": vertices,
                "lines": sorted(lines, key=lambda line: natural_key(line["slot"]))}
    _validate_topology(topology)
    _validate_template(template, topology)
    return topology, template


def _validate_topology(topology):
    vertices = topology["vertices"]
    lookup = {vertex["id"]: vertex for vertex in vertices}
    edges = topology["edges"]
    require(all(vertex["kind"] in ("external", "interaction") for vertex in vertices),
            "Unknown topology vertex kind")
    require(len(lookup) == len(vertices) and len(edges) == len(vertices) - 1,
            "Topology must be a tree")
    adjacency = {name: set() for name in lookup}
    edge_ids = set()
    for edge in edges:
        endpoints = edge["endpoints"]
        require(len(endpoints) == 2 and endpoints[0] != endpoints[1] and
                all(name in lookup for name in endpoints), "Invalid edge endpoints")
        source, target = endpoints
        require(edge["id"] == _edge_id(topology["id"], source, target) and
                edge["id"] not in edge_ids, "Invalid/duplicate edge ID")
        edge_ids.add(edge["id"])
        adjacency[source].add(target)
        adjacency[target].add(source)
        external = any(lookup[name]["kind"] == "external" for name in endpoints)
        require(edge["kind"] == ("external" if external else "internal"), "Invalid edge role")
    seen, pending = set(), [vertices[0]["id"]]
    while pending:
        name = pending.pop()
        if name not in seen:
            seen.add(name)
            pending.extend(adjacency[name] - seen)
    require(seen == set(lookup), "Disconnected topology")
    require(sum(vertex["kind"] == "external" for vertex in vertices) == 8,
            "Topology must have eight external vertices")
    for vertex in vertices:
        expected = 1 if vertex["kind"] == "external" else None
        require(len(adjacency[vertex["id"]]) == expected if expected else
                len(adjacency[vertex["id"]]) in (3, 4), "Invalid vertex valence")


def _validate_template(template, topology):
    edges = {edge["id"]: edge for edge in topology["edges"]}
    vertices = template["vertices"]
    require([{"id": vertex["id"], "kind": vertex["kind"]} for vertex in vertices] ==
            topology["vertices"], "Template vertex identity mismatch")
    require(all(math.isfinite(vertex["x"]) and math.isfinite(vertex["y"]) for vertex in vertices),
            "Non-finite vertex coordinates")
    lines = template["lines"]
    require(template["topology_id"] == topology["id"] and
            template["id"].split("-")[0] == topology["id"], "Wrong topology reference")
    require(len(lines) == len(edges) and {line["edge_id"] for line in lines} == set(edges),
            "Each topology edge must have exactly one slot")
    expected = {"E" + str(i) for i in range(1, 9)} | {
        "I" + str(i) for i in range(1, len(edges) - 7)}
    require({line["slot"] for line in lines} == expected, "Invalid line slots")
    for line in lines:
        edge = edges[line["edge_id"]]
        require(sorted((line["source"], line["target"])) == edge["endpoints"] and
                line["kind"] == edge["kind"] and
                line["slot"][0] == ("E" if edge["kind"] == "external" else "I"),
                "Slot/edge binding mismatch")
        require(line["statistics"] in ("F", "S") and
                line["line_type"] == ("fermion" if line["statistics"] == "F" else "scalar") and
                line["stroke_pattern"] == ("solid" if line["statistics"] == "F" else "dashed"),
                "Invalid Lorentz line style")
        require(len(line["label_position"]) == 2 and
                all(math.isfinite(value) for value in line["label_position"]), "Invalid label position")
        if line["arrow"]:
            require(sorted(line["arrow"].values()) == edge["endpoints"], "Invalid arrow endpoints")
        if "lm_edge_number" in line:
            number = -int(line["slot"][1:]) if line["kind"] == "external" else int(line["slot"][1:])
            vertex_lookup = {vertex["id"]: vertex for vertex in vertices}
            require(line["lm_edge_number"] == number and sorted(line["lm_endpoints"]) ==
                    sorted(vertex_lookup[endpoint]["lm_vertex_id"] for endpoint in edge["endpoints"]),
                    "LM edge/vertex binding mismatch")


def topology_catalog_id(catalog):
    payload = {key: catalog[key] for key in ("schema_version", "topologies", "templates")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_topology_catalog(catalog):
    require(catalog["schema_version"] == TOPOLOGY_SCHEMA_VERSION, "Unsupported topology schema")
    topology_lookup = {item["id"]: item for item in catalog["topologies"]}
    template_lookup = {item["id"]: item for item in catalog["templates"]}
    require(len(topology_lookup) == len(catalog["topologies"]) and
            len(template_lookup) == len(catalog["templates"]), "Duplicate topology/template ID")
    for topology in topology_lookup.values():
        _validate_topology(topology)
    for template in template_lookup.values():
        require(template["topology_id"] in topology_lookup, "Unknown topology")
        _validate_template(template, topology_lookup[template["topology_id"]])
    require(catalog["topology_catalog_id"] == topology_catalog_id(catalog), "Topology hash mismatch")


def build_topology_catalog(templates_root, model_catalog=None, lm_source_root=None):
    topologies, templates, manifest = {}, [], []
    paths = sorted(Path(templates_root).glob("T*-*.tex"), key=lambda path: natural_key(path.stem))
    require(paths, "No TeX diagram templates found")
    for path in paths:
        raw = path.read_bytes()
        topology, template = parse_tex_template(raw.decode("utf-8-sig"), path.stem)
        if topology["id"] in topologies:
            require(topologies[topology["id"]] == topology,
                    "Templates in a family have different graph connections: " + path.stem)
        else:
            topologies[topology["id"]] = topology
        templates.append(template)
        manifest.append({"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()})
    catalog = {"schema_version": TOPOLOGY_SCHEMA_VERSION,
               "topologies": list(topologies.values()), "templates": templates,
               "source_files": manifest}
    if model_catalog is not None:
        require(lm_source_root is not None, "LM source root is required to verify slot bindings")
        normalize_against_lm(catalog, model_catalog, lm_source_root)
    catalog["topology_catalog_id"] = topology_catalog_id(catalog)
    validate_topology_catalog(catalog)
    return catalog



def _lm_prototypes(source_root):
    prototypes, signatures, manifest = [], set(), []
    paths = sorted(Path(source_root).glob("LM*Left.m"), key=lambda path: natural_key(path.stem))
    require(paths, "No LM*Left.m graph sources")
    for path in paths:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        manifest.append({"path": str(path.resolve()), "sha256": digest})
        for block in re.split(r",\s*(?=Graph\[)", raw.decode("utf-8-sig")):
            fs_match = re.search(r'"FS"\s*->\s*<\|(.*?)\|>', block, re.S)
            edges_match = re.search(r'"EdgeLabels"\s*->\s*<\|(.*?)\|>', block, re.S)
            if not fs_match or not edges_match:
                continue
            fs = {int(i): value for i, value in re.findall(
                r'Edge\[(-?\d+)\]\s*->\s*"([FS])"', fs_match.group(1))}
            edges = {int(i): (int(a), int(b)) for i, a, b in re.findall(
                r'Edge\[(-?\d+)\]\s*->\s*DirectedEdge\[(\d+),\s*(\d+)\]',
                edges_match.group(1))}
            require(set(fs) == set(edges), "LM FS/edge-label mismatch: " + path.name)
            signature = (tuple(sorted(fs.items())), tuple(sorted(edges.items())))
            if signature in signatures:
                continue
            signatures.add(signature)
            notation = re.search(r'"DiaNotation"\s*->\s*"([^"]+)"', block)
            prototypes.append({"statistics": fs, "edges": edges,
                               "source": {"path": str(path.resolve()), "sha256": digest,
                                          "diagram_notation": notation.group(1) if notation else None}})
    require(prototypes, "No supported LM graph prototypes")
    return prototypes, manifest


def _lm_mapping(template, topology, prototype):
    edges = prototype["edges"]
    internal_vertices = sorted({v for number, endpoints in edges.items() if number > 0
                                for v in endpoints})
    template_vertices = {v["id"]: v for v in template["vertices"]}
    template_external = {line["slot"]: line for line in template["lines"]
                         if line["kind"] == "external"}
    external_signatures = {v: [] for v in internal_vertices}
    fixed = {}
    for number, endpoints in edges.items():
        if number >= 0:
            continue
        slot = "E" + str(-number)
        if slot not in template_external:
            return None
        source, target = endpoints
        if (source in external_signatures) == (target in external_signatures):
            return None
        interaction = source if source in external_signatures else target
        leaf = target if source in external_signatures else source
        external_signatures[interaction].append(slot)
        binding = template_external[slot]
        t_leaf = next(v for v in (binding["source"], binding["target"])
                      if template_vertices[v]["kind"] == "external")
        fixed[leaf] = t_leaf
    t_signatures = {v["id"]: [] for v in template["vertices"] if v["kind"] == "interaction"}
    for slot, line in template_external.items():
        interaction = next(v for v in (line["source"], line["target"]) if v in t_signatures)
        t_signatures[interaction].append(slot)
    source_groups, target_groups = {}, {}
    for vertex, slots in external_signatures.items():
        source_groups.setdefault(tuple(sorted(slots)), []).append(vertex)
    for vertex, slots in t_signatures.items():
        target_groups.setdefault(tuple(sorted(slots)), []).append(vertex)
    if set(source_groups) != set(target_groups) or any(
            len(vertices) != len(target_groups[key]) for key, vertices in source_groups.items()):
        return None
    groups = sorted(source_groups)
    permutations = [list(itertools.permutations(target_groups[key])) for key in groups]
    expected_edges = {tuple(edge["endpoints"]) for edge in topology["edges"]}
    matches = {}
    for choices in itertools.product(*permutations):
        mapping = dict(fixed)
        for key, vertices in zip(groups, choices):
            mapping.update(zip(source_groups[key], vertices))
        if {tuple(sorted((mapping[a], mapping[b]))) for a, b in edges.values()} != expected_edges:
            continue
        bindings = {("E" + str(-n) if n < 0 else "I" + str(n)):
                    _edge_id(topology["id"], mapping[a], mapping[b])
                    for n, (a, b) in edges.items()}
        matches[tuple(sorted(bindings.items()))] = (bindings, mapping)
    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def normalize_against_lm(registry, model_catalog, lm_source_root):
    prototypes, manifest = _lm_prototypes(lm_source_root)
    topologies = {t["id"]: t for t in registry["topologies"]}
    patterns = {}
    for diagram in model_catalog["diagrams"]:
        signature = {(-int(line["slot"][1:]) if line["slot"].startswith("E")
                      else int(line["slot"][1:])): line["statistics"]
                     for line in diagram["external_lines"] + diagram["internal_lines"]}
        previous = patterns.setdefault(diagram["template_id"], signature)
        require(previous == signature, "Template has variable E/I statistics: " + diagram["id"])
    all_corrections = []
    for template in registry["templates"]:
        require(template["id"] in patterns, "No model data for template: " + template["id"])
        desired = patterns[template["id"]]
        candidates = {}
        for prototype in prototypes:
            if prototype["statistics"] != desired:
                continue
            match = _lm_mapping(template, topologies[template["topology_id"]], prototype)
            if match:
                bindings, mapping = match
                candidates.setdefault(tuple(sorted(bindings.items())), (bindings, mapping, prototype))
        require(len(candidates) == 1, "No unique LM edge mapping for " + template["id"])
        bindings, mapping, prototype = next(iter(candidates.values()))
        slot_by_edge = {edge_id: slot for slot, edge_id in bindings.items()}
        template["lm_source"] = prototype["source"]
        for vertex in template["vertices"]:
            vertex["lm_vertex_id"] = next(v for v, target in mapping.items() if target == vertex["id"])
        corrections = []
        for line in template["lines"]:
            old_slot, old_statistics = line["slot"], line["statistics"]
            line["source_slot"] = old_slot
            line["source_statistics"] = old_statistics
            line["slot"] = slot_by_edge[line["edge_id"]]
            number = -int(line["slot"][1:]) if line["kind"] == "external" else int(line["slot"][1:])
            line["lm_edge_number"] = number
            line["lm_endpoints"] = list(prototype["edges"][number])
            line["statistics"] = desired[number]
            line["line_type"] = "fermion" if line["statistics"] == "F" else "scalar"
            line["stroke_pattern"] = "solid" if line["statistics"] == "F" else "dashed"
            if old_slot != line["slot"] or old_statistics != line["statistics"]:
                correction = {"template_id": template["id"], "edge_id": line["edge_id"],
                              "source_slot": old_slot, "slot": line["slot"],
                              "source_statistics": old_statistics, "statistics": line["statistics"]}
                corrections.append(correction)
                all_corrections.append(correction)
        template["lines"].sort(key=lambda line: natural_key(line["slot"]))
        template["normalization_corrections"] = corrections
        counts = Counter()
        for line in template["lines"]:
            if line["statistics"] == "F":
                counts[line["source"]] += 1
                counts[line["target"]] += 1
        require(all(counts[v["id"]] in (0, 2) for v in template["vertices"]
                    if v["kind"] == "interaction"),
                "Invalid fermion valence after attachment: " + template["id"])
    registry["lm_source_files"] = manifest
    registry["validated_model_catalog_id"] = model_catalog["catalog_id"]
    registry["normalization_corrections"] = all_corrections


def write_topology_catalog(catalog, output):
    validate_topology_catalog(catalog)
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_topology_catalog(path):
    catalog = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    validate_topology_catalog(catalog)
    return catalog
