"""
Print a Markdown summary of what changed between two copies of RENMAP/data.

Used by the pull request workflow to show reviewers what a PR does to the
map: nodes and links added, removed or changed, and counts per institution.

Usage: python RENMAP/scripts/summary.py BASE_DATA_DIR HEAD_DATA_DIR
"""
import json
import sys
from collections import Counter
from pathlib import Path

MAX_LISTED = 50


def load(data_dir):
    data_dir = Path(data_dir)
    if not (data_dir / "institutions.json").exists():
        return {}, {}, {}
    with open(data_dir / "institutions.json", encoding="utf-8") as f:
        institutions = {inst["id"]: inst for inst in json.load(f)}
    nodes = {}
    for file in sorted((data_dir / "nodes").glob("*.json")):
        with open(file, encoding="utf-8") as f:
            for node in json.load(f):
                nodes[node["name"]] = node
    links = {}
    for file in sorted((data_dir / "links").glob("*.json")):
        with open(file, encoding="utf-8") as f:
            for link in json.load(f):
                links[(link["a"], link["b"], tuple(sorted(link["owners"])))] = link
    return institutions, nodes, links


def link_label(key):
    a, b, owners = key
    return f"{a} – {b} ({', '.join(owners)})"


def bullet_list(title, items):
    items = sorted(items)
    if not items:
        return []
    lines = [f"**{title} ({len(items)})**", ""]
    lines += [f"- {item}" for item in items[:MAX_LISTED]]
    if len(items) > MAX_LISTED:
        lines.append(f"- … and {len(items) - MAX_LISTED} more")
    return lines + [""]


def counts_by_owner(elements):
    counter = Counter()
    for element in elements:
        for owner in element["owners"]:
            counter[owner] += 1
    return counter


def summarize(base_dir, head_dir):
    base_inst, base_nodes, base_links = load(base_dir)
    head_inst, head_nodes, head_links = load(head_dir)

    lines = ["## Topology changes", ""]

    changed_nodes = []
    for name in base_nodes.keys() & head_nodes.keys():
        old, new = base_nodes[name], head_nodes[name]
        diffs = [
            f"{field}: {old.get(field)!r} → {new.get(field)!r}"
            for field in ("lat", "lon", "owners", "networks")
            if old.get(field) != new.get(field)
        ]
        if diffs:
            changed_nodes.append(f"{name} ({'; '.join(diffs)})")

    changed_links = [
        f"{link_label(key)}: networks {base_links[key].get('networks')!r} → "
        f"{head_links[key].get('networks')!r}"
        for key in base_links.keys() & head_links.keys()
        if base_links[key].get("networks") != head_links[key].get("networks")
    ]

    sections = []
    sections += bullet_list(
        "Institutions added", [i["name"] for k, i in head_inst.items() if k not in base_inst]
    )
    sections += bullet_list(
        "Institutions removed", [i["name"] for k, i in base_inst.items() if k not in head_inst]
    )
    sections += bullet_list(
        "Institutions changed",
        [f"{k}: {base_inst[k]} → {head_inst[k]}"
         for k in base_inst.keys() & head_inst.keys() if base_inst[k] != head_inst[k]],
    )
    sections += bullet_list("Nodes added", head_nodes.keys() - base_nodes.keys())
    sections += bullet_list("Nodes removed", base_nodes.keys() - head_nodes.keys())
    sections += bullet_list("Nodes changed", changed_nodes)
    sections += bullet_list(
        "Links added", [link_label(k) for k in head_links.keys() - base_links.keys()]
    )
    sections += bullet_list(
        "Links removed", [link_label(k) for k in base_links.keys() - head_links.keys()]
    )
    sections += bullet_list("Links changed", changed_links)

    if sections:
        lines += sections
    else:
        lines += ["No changes to nodes, links or institutions.", ""]

    base_node_counts = counts_by_owner(base_nodes.values())
    head_node_counts = counts_by_owner(head_nodes.values())
    base_link_counts = counts_by_owner(base_links.values())
    head_link_counts = counts_by_owner(head_links.values())

    def cell(old, new):
        return str(new) if old == new else f"{old} → **{new}**"

    lines += [
        "<details><summary>Nodes and links per institution</summary>",
        "",
        "| Institution | Nodes | Links |",
        "| --- | --- | --- |",
    ]
    for inst_id in sorted(base_inst.keys() | head_inst.keys()):
        name = (head_inst.get(inst_id) or base_inst[inst_id])["name"]
        lines.append(
            f"| {name} (`{inst_id}`) "
            f"| {cell(base_node_counts[inst_id], head_node_counts[inst_id])} "
            f"| {cell(base_link_counts[inst_id], head_link_counts[inst_id])} |"
        )
    lines += [
        f"| **Total** | {cell(len(base_nodes), len(head_nodes))} "
        f"| {cell(len(base_links), len(head_links))} |",
        "",
        "</details>",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())
    print(summarize(sys.argv[1], sys.argv[2]))
