"""Stateless matching against the entire selected field set."""
import copy
import re
from pathlib import Path

from .catalog import fieldset_key, load_catalog, validate_catalog


class InvalidFieldError(ValueError):
    pass


class MatchingEngine:
    def __init__(self, catalog, topology_catalog=None):
        # A caller cannot silently change the data behind an existing index.
        self._catalog = copy.deepcopy(catalog)
        validate_catalog(self._catalog)
        self.catalog_id = self._catalog["catalog_id"]
        self._fields = {field["id"]: field for field in self._catalog["fields"]}
        self._models = self._catalog["models"]
        self._model_lookup = {model["id"]: model for model in self._models}
        self._diagrams = {diagram["id"]: diagram for diagram in self._catalog["diagrams"]}
        position = {model["id"]: i for i, model in enumerate(self._models)}
        self._model_position = position
        self._model_aliases = self._catalog["indexes"]["model_aliases"]
        self._diagram_position = {diagram["id"]: i for i, diagram in
                                  enumerate(self._catalog["diagrams"])}
        self._by_field = {
            int(field_id): frozenset(position[model_id] for model_id in model_ids)
            for field_id, model_ids in self._catalog["indexes"]["field_to_models"].items()
        }
        self._by_fieldset = self._catalog["indexes"]["fieldset_to_model"]
        self._all = frozenset(range(len(self._models)))
        self._minimal = frozenset(i for i, model in enumerate(self._models) if model["minimal"])
        self._attachment_system = None
        self._topology_catalog = topology_catalog
        self._topology_path = None

    @classmethod
    def from_file(cls, path=None, topology_path=None):
        if path is None:
            path = Path(__file__).resolve().parents[1] / "data" / "catalog.json"
        engine = cls(load_catalog(path))
        engine._topology_path = Path(topology_path) if topology_path else Path(path).parent / "topologies.json"
        return engine

    def _field_id(self, value):
        if type(value) is int:
            field_id = value
        elif isinstance(value, str) and re.fullmatch(r"[1-9]\d*(?:\^\*|\^C)?", value.strip()):
            token = value.strip()
            field_id = int(token[:-2] if token.endswith(("^*", "^C")) else token)
        else:
            raise InvalidFieldError("Field IDs must be positive integers or numbered conjugates")
        if field_id not in self._fields:
            raise InvalidFieldError("Unknown field ID: {}".format(field_id))
        return field_id

    def normalize_fields(self, selected_fields):
        if isinstance(selected_fields, (str, bytes)) or selected_fields is None:
            raise InvalidFieldError("Pass a collection of field IDs, for example [1, 52, 56]")
        try:
            return tuple(sorted({self._field_id(value) for value in selected_fields}))
        except TypeError as exc:
            raise InvalidFieldError("Selected fields must be an iterable of field IDs") from exc

    def _compatible(self, selected):
        if not selected:
            return self._all
        pools = sorted((self._by_field[field_id] for field_id in selected), key=len)
        compatible = pools[0]
        for pool in pools[1:]:
            compatible = compatible.intersection(pool)
            if not compatible:
                break
        return compatible

    def _ids(self, positions):
        return [self._models[position]["id"] for position in sorted(positions)]

    def _model_field_ids(self, positions):
        return [self._models[i]["model_field_id"] for i in sorted(positions)
                if self._models[i]["model_field_id"] is not None]

    def _model_diagram_ids(self, positions):
        ids = [diagram_id for i in positions for diagram_id in self._models[i]["diagram_ids"]]
        return sorted(ids, key=self._diagram_position.__getitem__)

    def _diagram_count(self, positions):
        return sum(self._models[position]["diagram_count"] for position in positions)

    def summary(self):
        return {"schema_version": self._catalog["schema_version"],
                "catalog_id": self.catalog_id,
                **copy.deepcopy(self._catalog["metadata"])}

    def fields(self):
        return copy.deepcopy(self._catalog["fields"])

    def field(self, field_id):
        return copy.deepcopy(self._fields[self._field_id(field_id)])

    def model(self, model_id):
        canonical_id = self._model_aliases.get(model_id)
        if canonical_id is None:
            raise ValueError("Unknown model ID: {}".format(model_id))
        return copy.deepcopy(self._model_lookup[canonical_id])

    def model_field(self, model_field_id):
        if not isinstance(model_field_id, str) or not re.fullmatch(
                r"MF-[345]i-[1-9]\d*", model_field_id):
            raise ValueError("A model-field ID must be a published MF-3i/4i/5i number")
        model = self.model(model_field_id)
        if model["model_field_id"] != model_field_id:
            raise ValueError("Unknown published model-field ID: " + model_field_id)
        return model

    def model_diagram(self, model_diagram_id, include_attachment=False):
        diagram = self.diagram(model_diagram_id)
        if include_attachment:
            diagram["topology_attachment"] = self.attachment(model_diagram_id)
        return diagram

    def _attachment_backend(self):
        if self._attachment_system is None:
            from .attachments import AttachmentSystem
            from .topology import load_topology_catalog
            registry = self._topology_catalog
            if registry is None:
                if self._topology_path is None or not self._topology_path.is_file():
                    raise ValueError("Build data/topologies.json before requesting an attachment")
                registry = load_topology_catalog(self._topology_path)
            self._attachment_system = AttachmentSystem(self._catalog, registry)
        return self._attachment_system

    def attachment(self, model_diagram_id):
        return self._attachment_backend().attach(model_diagram_id)

    def topology(self, topology_id):
        return self._attachment_backend().topology(topology_id)

    def diagram_template(self, template_id):
        return self._attachment_backend().template(template_id)

    def validate_attachments(self):
        return self._attachment_backend().validate_all()

    def diagram(self, diagram_id):
        if diagram_id not in self._diagrams:
            raise ValueError("Unknown model-diagram ID: {}".format(diagram_id))
        diagram = copy.deepcopy(self._diagrams[diagram_id])
        field_to_internal_lines = {}
        for line in diagram["internal_lines"]:
            if line["kind"] == "bsm":
                field_to_internal_lines.setdefault(str(line["field_id"]), []).append(line["slot"])
        diagram["field_to_internal_lines"] = field_to_internal_lines
        return diagram

    def matching_models(self, selected_fields, complete=False, minimal_only=False):
        selected = self.normalize_fields(selected_fields)
        if complete:
            model_id = self._by_fieldset.get(fieldset_key(selected))
            ids = [model_id] if model_id else []
            if minimal_only:
                ids = [model_id for model_id in ids if self._model_lookup[model_id]["minimal"]]
            return ids
        positions = self._compatible(selected)
        if minimal_only:
            positions = positions.intersection(self._minimal)
        return self._ids(positions)

    def field_compatibility(self, left, right):
        left, right = self._field_id(left), self._field_id(right)
        positions = self._by_field[left].intersection(self._by_field[right])
        minimal = positions.intersection(self._minimal)
        return {
            "catalog_id": self.catalog_id,
            "field_ids": list(sorted({left, right})),
            "compatible": bool(positions),
            "compatible_model_ids": self._ids(positions),
            "compatible_model_field_ids": self._model_field_ids(positions),
            "compatible_model_diagram_ids": self._model_diagram_ids(positions),
            "compatible_model_count": len(positions),
            "compatible_minimal_model_ids": self._ids(minimal),
            "compatible_minimal_model_count": len(minimal),
            "compatible_diagram_count": self._diagram_count(positions),
        }

    def field_neighbors(self, field_id):
        field_id = self._field_id(field_id)
        result = self.match([field_id])
        return {"field": self.field(field_id), "catalog_id": self.catalog_id,
                "compatible_model_ids": result["compatible_model_ids"],
                "compatible_model_field_ids": result["compatible_model_field_ids"],
                "compatible_model_diagram_ids": result["compatible_model_diagram_ids"],
                "next_fields": {key: state for key, state in result["next_fields"].items()
                                if int(key) != field_id}}

    def match(self, selected_fields, request_id=None):
        """Return exact matches, completion candidates and all next-field states.

        Cancellation/undo simply calls this method with the new complete selection.
        request_id is echoed so clients can discard stale asynchronous responses.
        """
        if request_id is not None and not isinstance(request_id, str):
            raise ValueError("request_id must be a string or None")
        selected = self.normalize_fields(selected_fields)
        selected_set = set(selected)
        compatible = self._compatible(selected)
        compatible_minimal = compatible.intersection(self._minimal)
        complete_id = self._by_fieldset.get(fieldset_key(selected))
        complete = [complete_id] if complete_id else []
        complete_minimal = [model_id for model_id in complete
                            if self._model_lookup[model_id]["minimal"]]
        if not selected:
            status, minimum = "initial", None
        elif complete_minimal:
            status, minimum = "ready_minimal", 0
        elif complete:
            status, minimum = "ready_model", 0
        elif compatible:
            status = "pending"
            minimum = min(len(self._models[i]["field_ids"]) - len(selected) for i in compatible)
        else:
            status, minimum = "incompatible", None
        next_fields = {}
        for field_id in sorted(self._fields):
            positions = compatible.intersection(self._by_field[field_id])
            minimal = positions.intersection(self._minimal)
            if field_id in selected_set:
                state, color = "selected", None
            elif not selected:
                state, color = "initial", "white"
            elif not positions:
                state, color = "hidden", None
            else:
                state, color = "available", "red" if minimal else "green"
            next_fields[str(field_id)] = {
                "state": state, "color": color,
                "compatible_model_count": len(positions),
                "compatible_minimal_model_count": len(minimal),
            }
        generation_ids = complete_minimal or complete
        generation_kind = ("minimal" if complete_minimal else "model") if generation_ids else None
        complete_positions = {self._model_position[model_id] for model_id in complete}
        generation_positions = {self._model_position[model_id] for model_id in generation_ids}
        return {
            "catalog_id": self.catalog_id, "request_id": request_id,
            "selected_field_ids": list(selected), "status": status,
            "can_generate": bool(generation_ids), "min_additional_fields": minimum,
            "compatible_model_ids": self._ids(compatible),
            "compatible_model_field_ids": self._model_field_ids(compatible),
            "compatible_model_diagram_ids": self._model_diagram_ids(compatible),
            "compatible_model_count": len(compatible),
            "compatible_minimal_model_ids": self._ids(compatible_minimal),
            "compatible_minimal_model_count": len(compatible_minimal),
            "compatible_diagram_count": self._diagram_count(compatible),
            "complete_model_ids": complete, "complete_model_count": len(complete),
            "complete_model_field_ids": self._model_field_ids(complete_positions),
            "complete_model_diagram_ids": self._model_diagram_ids(complete_positions),
            "complete_minimal_model_ids": complete_minimal,
            "complete_diagram_count": sum(self._model_lookup[i]["diagram_count"] for i in complete),
            "generation": {
                "kind": generation_kind, "model_ids": generation_ids,
                "model_field_ids": self._model_field_ids(generation_positions),
                "model_diagram_ids": self._model_diagram_ids(generation_positions),
                "internal_model_ids": [self._model_lookup[i]["internal_id"]
                                       for i in generation_ids],
                "model_count": len(generation_ids),
                "diagram_count": sum(self._model_lookup[i]["diagram_count"] for i in generation_ids),
            },
            "next_fields": next_fields,
        }
