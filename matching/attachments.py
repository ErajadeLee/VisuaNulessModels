"""Attach an exact model-diagram to a topology using its published E/I slots."""
import copy
from fractions import Fraction

from .catalog import SM_FIELDS, natural_key
from .topology import require, validate_topology_catalog


def display_label(line):
    base = str(line["field_id"]) if line["kind"] == "bsm" else line["sm_symbol"]
    return base + ("^*" if line["conjugated"] else "")


def _quantum(su3, su2, hypercharge):
    p, q = su3
    y = Fraction(hypercharge)
    return {"su3": {"dynkin": list(su3), "dimension": (p + 1) * (q + 1) * (p + q + 2) // 2},
            "su2": {"dynkin": list(su2), "dimension": su2[0] + 1},
            "hypercharge": {"numerator": y.numerator, "denominator": y.denominator, "text": str(y)}}


class AttachmentSystem:
    def __init__(self, model_catalog, topology_catalog):
        validate_topology_catalog(topology_catalog)
        require(topology_catalog.get("validated_model_catalog_id", model_catalog["catalog_id"]) ==
                model_catalog["catalog_id"], "Topology registry was built for a different model catalog")
        self.catalog_id = model_catalog["catalog_id"]
        self.topology_catalog_id = topology_catalog["topology_catalog_id"]
        self._fields = {field["id"]: field for field in model_catalog["fields"]}
        self._models = {model["id"]: model for model in model_catalog["models"]}
        self._diagrams = {diagram["id"]: diagram for diagram in model_catalog["diagrams"]}
        self._topologies = {topology["id"]: topology for topology in topology_catalog["topologies"]}
        self._templates = {template["id"]: template for template in topology_catalog["templates"]}

    def topology(self, topology_id):
        require(topology_id in self._topologies, "Unknown topology ID: " + str(topology_id))
        return copy.deepcopy(self._topologies[topology_id])

    def template(self, template_id):
        require(template_id in self._templates, "Unknown diagram template: " + str(template_id))
        return copy.deepcopy(self._templates[template_id])

    def check_diagram(self, diagram):
        require(diagram["template_id"] in self._templates,
                "Missing template for " + diagram["id"])
        template = self._templates[diagram["template_id"]]
        lines = {line["slot"]: line for line in diagram["external_lines"] + diagram["internal_lines"]}
        require(set(lines) == {line["slot"] for line in template["lines"]},
                "Attachment slots do not cover template: " + diagram["id"])
        for binding in template["lines"]:
            assignment = lines[binding["slot"]]
            require(binding["statistics"] == assignment["statistics"],
                    "Lorentz statistics mismatch: {} {}".format(diagram["id"], binding["slot"]))

    def validate_all(self):
        used_templates = {diagram["template_id"] for diagram in self._diagrams.values()}
        require(used_templates == set(self._templates),
                "Model catalog and topology templates do not have the same coverage")
        for diagram in self._diagrams.values():
            self.check_diagram(diagram)
        return {"topology_count": len(self._topologies), "template_count": len(self._templates),
                "validated_model_diagram_count": len(self._diagrams)}

    def _field_assignment(self, line):
        if line["kind"] == "bsm":
            field = self._fields[line["field_id"]]
            su3, su2 = field["su3"]["dynkin"], field["su2"]["dynkin"]
            y = Fraction(field["hypercharge"]["numerator"], field["hypercharge"]["denominator"])
        else:
            su3, su2, y, _ = SM_FIELDS[line["sm_symbol"]]
        effective3 = list(reversed(su3)) if line["conjugated"] else list(su3)
        effective_y = -y if line["conjugated"] else y
        return {
            **copy.deepcopy(line), "display_label": display_label(line),
            "canonical_quantum": _quantum(su3, su2, y),
            "attached_quantum": _quantum(effective3, su2, effective_y),
        }

    def attach(self, model_diagram_id):
        require(model_diagram_id in self._diagrams,
                "Unknown model-diagram ID: " + str(model_diagram_id))
        diagram = self._diagrams[model_diagram_id]
        self.check_diagram(diagram)
        template = self._templates[diagram["template_id"]]
        topology = self._topologies[template["topology_id"]]
        assignments = {line["slot"]: line for line in
                       diagram["external_lines"] + diagram["internal_lines"]}
        attached_lines, by_field, by_edge, vertex_attachments = [], {}, {}, {}
        vertices = copy.deepcopy(template["vertices"])
        vertex_lookup = {vertex["id"]: vertex for vertex in vertices}
        for vertex in vertices:
            vertex["incident_slots"] = []
            if vertex["kind"] == "interaction":
                vertex_attachments[vertex["id"]] = {"external_slots": [], "internal_slots": []}
        for binding in template["lines"]:
            assignment = self._field_assignment(assignments[binding["slot"]])
            attached = {**copy.deepcopy(binding), "field": assignment}
            attached_lines.append(attached)
            by_edge[binding["edge_id"]] = binding["slot"]
            for endpoint in (binding["source"], binding["target"]):
                vertex = vertex_lookup[endpoint]
                vertex["incident_slots"].append(binding["slot"])
                if vertex["kind"] == "external":
                    vertex["attached_slot"] = binding["slot"]
                else:
                    role = "external_slots" if binding["kind"] == "external" else "internal_slots"
                    vertex_attachments[endpoint][role].append(binding["slot"])
            if assignment["kind"] == "bsm":
                by_field.setdefault(str(assignment["field_id"]), []).append(binding["slot"])
        for vertex in vertices:
            vertex["incident_slots"].sort(key=natural_key)
        for values in vertex_attachments.values():
            for slots in values.values():
                slots.sort(key=natural_key)
        model = self._models[diagram["model_id"]]
        return {
            "catalog_id": self.catalog_id, "topology_catalog_id": self.topology_catalog_id,
            "model_diagram_id": diagram["id"], "model_field_id": diagram["model_field_id"],
            "model_id": model["id"], "field_ids": list(model["field_ids"]),
            "minimal": model["minimal"], "topology_id": topology["id"],
            "template_id": template["id"],
            "pipeline": [{"stage": "topology", "id": topology["id"]},
                         {"stage": "diagram", "id": template["id"]},
                         {"stage": "attachment", "id": diagram["id"]}],
            "topology": copy.deepcopy(topology),
            "attachment": {"vertices": vertices, "lines": attached_lines,
                           "vertex_attachments": vertex_attachments},
            "slot_to_edge": {line["slot"]: line["edge_id"] for line in attached_lines},
            "edge_to_slot": by_edge, "field_to_lines": by_field,
            "field_to_edges": {field_id: [next(line["edge_id"] for line in attached_lines
                                             if line["slot"] == slot) for slot in slots]
                               for field_id, slots in by_field.items()},
        }
