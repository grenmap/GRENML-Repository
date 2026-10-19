"""
Validate the RENMAP JSON data before generating GRENML.

Checks every file in RENMAP/data, reports all problems at once (file and
item index) and exits with status 1 if any errors were found; warnings
are printed but don't fail. When the data is
consistent it also runs the generator into a temporary directory, so
errors raised by the grenml library itself show up here too.

Usage: uv run --project RENMAP RENMAP/scripts/validate.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RENMAP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = RENMAP_DIR / "data"
GENERATE_SCRIPT = Path(__file__).resolve().parent / "generate.py"

VALID_TAGS = {"nren", "pren"}

INSTITUTION_FIELDS = {"id": str, "name": str, "tag": str}
NODE_FIELDS = {"name": str, "lat": (int, float), "lon": (int, float),
               "owners": list, "networks": str}
LINK_FIELDS = {"a": str, "b": str, "owners": list, "networks": str}

TYPE_NAMES = {str: "a string", list: "a list", (int, float): "a number"}


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, where, message):
        self.errors.append(f"{where}: {message}")

    def warning(self, where, message):
        self.warnings.append(f"{where}: {message}")


def rel(path):
    try:
        return path.relative_to(RENMAP_DIR.parent)
    except ValueError:
        return path


def load_list(path, report):
    """Load a JSON file that must contain a list; None if it can't be used."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        report.error(rel(path), f"invalid JSON (line {e.lineno}, column {e.colno}): {e.msg}")
        return None
    if not isinstance(data, list):
        report.error(rel(path), "the file must contain a JSON list ([ ... ])")
        return None
    return data


def check_fields(item, fields, where, report):
    """Check required fields and their types. True if the item is usable."""
    if not isinstance(item, dict):
        report.error(where, "each item must be a JSON object ({ ... })")
        return False
    ok = True
    for field, expected in fields.items():
        if field not in item:
            report.error(where, f'missing required field "{field}"')
            ok = False
            continue
        value = item[field]
        # bool is a subclass of int; a coordinate of true/false is a mistake
        if not isinstance(value, expected) or isinstance(value, bool):
            report.error(
                where, f'field "{field}" must be {TYPE_NAMES[expected]}, got {value!r}'
            )
            ok = False
    for field in item.keys() - fields.keys():
        report.error(where, f'unknown field "{field}"')
    return ok


def check_owners(owners, institution_ids, where, report):
    if not owners:
        report.error(where, '"owners" must not be empty')
    for owner in owners:
        if owner not in institution_ids:
            report.error(where, f'owner "{owner}" is not defined in data/institutions.json')
    if len(set(owners)) != len(owners):
        report.error(where, '"owners" has repeated entries')


def validate(data_dir=DATA_DIR):
    report = Report()

    # Institutions
    institutions_path = data_dir / "institutions.json"
    institution_ids = set()
    institution_names = set()
    if not institutions_path.exists():
        report.error(rel(institutions_path), "file not found")
    else:
        for i, inst in enumerate(load_list(institutions_path, report) or []):
            where = f"{rel(institutions_path)}[{i}]"
            if not check_fields(inst, INSTITUTION_FIELDS, where, report):
                continue
            if inst["tag"] not in VALID_TAGS:
                report.error(
                    where, f'"tag" must be one of {sorted(VALID_TAGS)}, got "{inst["tag"]}"'
                )
            if inst["id"] in institution_ids:
                report.error(where, f'id "{inst["id"]}" is already used')
            if inst["name"] in institution_names:
                report.error(where, f'name "{inst["name"]}" is already used')
            institution_ids.add(inst["id"])
            institution_names.add(inst["name"])

    # Nodes
    node_names = {}
    for path in sorted((data_dir / "nodes").glob("*.json")):
        for i, node in enumerate(load_list(path, report) or []):
            where = f"{rel(path)}[{i}]"
            # Register the name even if other fields are broken, so links to
            # this node don't pile up follow-on "node doesn't exist" errors.
            name = node.get("name") if isinstance(node, dict) else None
            if isinstance(name, str):
                if name in node_names:
                    report.error(where, f'node "{name}" is already defined at {node_names[name]}')
                else:
                    node_names[name] = where
            if not check_fields(node, NODE_FIELDS, where, report):
                continue
            if not -90 <= node["lat"] <= 90:
                report.error(where, f'"lat" out of range [-90, 90]: {node["lat"]}')
            if not -180 <= node["lon"] <= 180:
                report.error(where, f'"lon" out of range [-180, 180]: {node["lon"]}')
            check_owners(node["owners"], institution_ids, where, report)

    # Links
    seen_links = {}
    for path in sorted((data_dir / "links").glob("*.json")):
        for i, link in enumerate(load_list(path, report) or []):
            where = f"{rel(path)}[{i}]"
            if not check_fields(link, LINK_FIELDS, where, report):
                continue
            for end in ("a", "b"):
                if link[end] not in node_names:
                    report.error(where, f'node "{link[end]}" (field "{end}") is not defined in data/nodes')
            if link["a"] == link["b"]:
                report.error(where, f'link connects node "{link["a"]}" to itself')
            # Same endpoints in the same order produce the same GRENML ID, so
            # that is an error. The reverse order (b -> a) gets a different ID
            # and may be a parallel circuit, so it is only flagged.
            key = (link["a"], link["b"], frozenset(link["owners"]))
            reverse_key = (link["b"], link["a"], frozenset(link["owners"]))
            if key in seen_links:
                report.error(where, f"duplicate link (same as {seen_links[key]})")
            else:
                seen_links[key] = where
                if reverse_key in seen_links:
                    report.warning(
                        where,
                        f"same link as {seen_links[reverse_key]} in the opposite direction; "
                        "if it is not a parallel circuit, remove one of them",
                    )
            check_owners(link["owners"], institution_ids, where, report)

    return report, len(institution_ids), len(node_names), len(seen_links)


def check_generation():
    """Run the generator in a scratch directory; return its error output, if any."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(GENERATE_SCRIPT), "--output-dir", tmp],
            capture_output=True, text=True,
        )
    if result.returncode != 0:
        return (result.stdout + result.stderr).strip()
    return None


def main():
    report, n_institutions, n_nodes, n_links = validate()
    if report.warnings:
        print(f"{len(report.warnings)} warning(s):\n")
        for warning in report.warnings:
            print(f"  - {warning}")
        print()
    if report.errors:
        print(f"Found {len(report.errors)} problem(s) in the data:\n")
        for error in report.errors:
            print(f"  - {error}")
        sys.exit(1)

    generation_error = check_generation()
    if generation_error:
        print("The data passed validation, but generating the GRENML failed:\n")
        print(generation_error)
        sys.exit(1)

    print(f"OK: {n_institutions} institutions, {n_nodes} nodes, {n_links} links.")


if __name__ == "__main__":
    main()
