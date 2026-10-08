"""Run from the project root: python -m examples.query"""
import json

from matching import MatchingEngine

engine = MatchingEngine.from_file()
for selection in ([1], [1, 52, 56], [13, 30, 40, 48], [30, 40, 48]):
    result = engine.match(selection, request_id="example")
    print(json.dumps({
        "selected_field_ids": result["selected_field_ids"],
        "status": result["status"],
        "compatible_model_count": result["compatible_model_count"],
        "complete_model_count": result["complete_model_count"],
        "model_field_ids": result["complete_model_field_ids"],
        "model_diagram_ids": result["complete_model_diagram_ids"],
        "complete_diagram_count": result["complete_diagram_count"],
        "min_additional_fields": result["min_additional_fields"],
        "generation": result["generation"],
    }, ensure_ascii=False, indent=2))
