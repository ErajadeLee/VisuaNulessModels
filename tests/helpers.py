import tempfile
from pathlib import Path

from matching.catalog import build_catalog


def fixture_catalog(field_sets, field_count=5, tokens_override=None,
                    reference_ids=None, supplementary_transform=None):
    """Use tiny real-format Wolfram exports and optional numbered reference tables."""
    with tempfile.TemporaryDirectory(prefix="0nbb-matching-test-") as directory:
        root = Path(directory)
        fields = ["{{{0,0},{0},%d},\"S\",\"C\",1}" % (-i)
                  for i in range(1, field_count + 1)]
        (root / "allnewfield.m").write_text("{" + ",".join(fields) + "}", encoding="utf-8")
        exports = root / "TopoAssignedOutInLines" / "formatm"
        exports.mkdir(parents=True)
        rows, column_rows = [], []
        for index, field_ids in enumerate(field_sets, 1):
            tokens = [str(field_id) for field_id in field_ids]
            if tokens_override and index in tokens_override:
                tokens = tokens_override[index]
            assert len(tokens) <= 4
            tokens += ["H"] * (4 - len(tokens))
            columns = ["T1-1-{}".format(index)] + ["H"] * 8 + tokens
            column_rows.append(columns)
            rows.append('"' + "&".join(columns) + '"')
        (exports / "T1-1.m").write_text("{" + ",".join(rows) + "}", encoding="utf-8")
        supplementary = None
        if reference_ids is not None:
            groups = {}
            for columns in column_rows:
                ids = tuple(sorted({int(token[:-2] if token.endswith(("^*", "^C")) else token)
                                    for token in columns[9:]
                                    if token.rstrip("^*C").isdigit()}))
                groups.setdefault(ids, []).append(columns[0])
            document_rows = []
            for columns in column_rows:
                ids = next(ids for ids, diagrams in groups.items() if columns[0] in diagrams)
                minimal = not any(set(candidate) < set(ids) for candidate in groups)
                flag = r"\ding{51}" if minimal else r"\ding{55}"
                document_rows.append("&".join([columns[0], flag] +
                                              ["$" + token + "$" for token in columns[1:]])
                                     + r"\\\hline")
            for ids, reference_id in reference_ids.items():
                document_rows.append(reference_id + "&" +
                                     r",\,".join(str(i) for i in ids) + "&" +
                                     r",\,".join(groups[ids]) + r"\\\hline")
            document = "\n".join(document_rows) + "\n"
            if supplementary_transform:
                document = supplementary_transform(document)
            supplementary = root / "supplementary.tex"
            supplementary.write_text(document, encoding="utf-8")
        return build_catalog(root, supplementary=supplementary)
