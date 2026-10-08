"""Render the fixed graph and its E/I attachments as an interactive SVG."""
import html
import math


def _e(value):
    return html.escape(str(value), quote=True)


def _label_text(label):
    label = label.replace("ell_L", "\u2113_L")
    conjugated = label.endswith("^*")
    base = label[:-2] if conjugated else label
    if "_" in base:
        head, subscript = base.split("_", 1)
        output = _e(head) + '<tspan baseline-shift="sub" font-size=".22">' + _e(subscript) + "</tspan>"
    else:
        output = _e(base)
    if conjugated:
        output += '<tspan baseline-shift="super" font-size=".22">*</tspan>'
    return output


def render_svg(packet, stage="attachment"):
    if stage not in ("topology", "diagram", "attachment"):
        raise ValueError("stage must be topology, diagram or attachment")
    vertices = packet["attachment"]["vertices"]
    lookup = {vertex["id"]: vertex for vertex in vertices}
    lines = packet["attachment"]["lines"]
    points = [(v["x"], -v["y"]) for v in vertices] + [
        (line["label_position"][0], -line["label_position"][1]) for line in lines]
    left, top = min(p[0] for p in points) - 0.85, min(p[1] for p in points) - 0.85
    width = max(p[0] for p in points) - left + 0.85
    height = max(p[1] for p in points) - top + 0.85
    output = [
        '<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{}" '
        'data-model-diagram-id="{}" viewBox="{} {} {} {}">'.format(
            _e(packet["model_diagram_id"] + " " + stage), _e(packet["model_diagram_id"]),
            left, top, width, height),
        "<style>.wire{fill:none;stroke:#243448;stroke-width:.032;stroke-linecap:round}"
        ".arrow{fill:#243448}.label{font-family:Georgia,'Times New Roman',serif;"
        "font-size:.33px;fill:#162940;paint-order:stroke;stroke:white;stroke-width:.055}"
        ".edge .hit{stroke:transparent;stroke-width:.24;fill:none;pointer-events:stroke}"
        # Chromium scales its native focus outline in SVG user units; use wire highlighting instead.
        ".edge{cursor:pointer;outline:none}.edge:hover .wire,.edge:focus-visible .wire,.edge.active .wire{stroke:#1565c0;stroke-width:.06}"
        ".edge:hover .arrow,.edge:focus-visible .arrow,.edge.active .arrow{fill:#1565c0}"
        ".edge:hover .label,.edge:focus-visible .label,.edge.active .label{fill:#1565c0}</style>",
    ]
    for line in lines:
        a, b = lookup[line["source"]], lookup[line["target"]]
        x1, y1, x2, y2 = a["x"], -a["y"], b["x"], -b["y"]
        field = line["field"]
        y = field["attached_quantum"]["hypercharge"]["text"]
        title = "{}: {} | {} | SU(3) {} | SU(2) {} | Y={}".format(
            line["slot"], field["display_label"], field["statistics"],
            field["attached_quantum"]["su3"]["dynkin"],
            field["attached_quantum"]["su2"]["dimension"], y)
        output.append(
            '<g class="edge" id="line-{}" tabindex="0" data-line-slot="{}" '
            'data-edge-id="{}" data-field-id="{}" data-sm-symbol="{}"><title>{}</title>'.format(
                line["slot"], line["slot"], _e(line["edge_id"]),
                field["field_id"] if field["field_id"] is not None else "",
                _e(field["sm_symbol"] or ""), _e(title)))
        dash = ' stroke-dasharray=".10 .075"' if stage != "topology" and field["statistics"] == "S" else ""
        output.append('<line class="wire" x1="{}" y1="{}" x2="{}" y2="{}"{}/>'.format(
            x1, y1, x2, y2, dash))
        if stage != "topology" and line["arrow"]:
            arrow_start = lookup[line["arrow"]["source"]]
            arrow_end = lookup[line["arrow"]["target"]]
            dx, dy = arrow_end["x"] - arrow_start["x"], -(arrow_end["y"] - arrow_start["y"])
            length = math.hypot(dx, dy)
            ux, uy = dx / length, dy / length
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            triangle = [(mx + ux * .14, my + uy * .14),
                        (mx - ux * .075 - uy * .065, my - uy * .075 + ux * .065),
                        (mx - ux * .075 + uy * .065, my - uy * .075 - ux * .065)]
            output.append('<polygon class="arrow" points="{}"/>'.format(
                " ".join("{},{}".format(x, y) for x, y in triangle)))
        if stage != "topology":
            label = line["slot"] if stage == "diagram" else field["display_label"]
            if stage == "diagram":
                label = label[0] + "_" + label[1:]
            x, y = line["label_position"]
            output.append('<text class="label" id="label-{}" x="{}" y="{}" '
                          'text-anchor="middle" dominant-baseline="central">{}</text>'.format(
                              line["slot"], x, -y, _label_text(label)))
        output.append('<line class="hit" x1="{}" y1="{}" x2="{}" y2="{}"/></g>'.format(
            x1, y1, x2, y2))
    for vertex in vertices:
        radius = .045 if vertex["kind"] == "interaction" else .025
        output.append('<circle id="vertex-{}" cx="{}" cy="{}" r="{}" fill="#243448"/>'.format(
            _e(vertex["id"]), vertex["x"], -vertex["y"], radius))
    output.append("</svg>")
    return "\n".join(output)
