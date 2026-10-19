"""
Generate the RENMAP GRENML files from the JSON data in RENMAP/data.

Writes:
  RENMAP/topologies.xml                  every network together
  RENMAP/topologies/<tag>/<id>.xml       one file per institution that owns links

Usage: uv run --project RENMAP RENMAP/scripts/generate.py [--output-dir DIR]
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import grenml
from grenml.models import Institution, Node, Link

RENMAP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = RENMAP_DIR / "data"

COMBINED_NAME = "Topology"
COMBINED_OWNER = "redclara"


def load_data(data_dir=DATA_DIR):
    """
    Load institutions, nodes (keyed by name) and links from the JSON
    files. Files are read in sorted order so the output is stable.
    """
    with open(data_dir / "institutions.json", encoding="utf-8") as f:
        institutions = json.load(f)

    nodes = {}
    for file in sorted((data_dir / "nodes").glob("*.json")):
        with open(file, encoding="utf-8") as f:
            for node in json.load(f):
                nodes[node["name"]] = node

    links = []
    for file in sorted((data_dir / "links").glob("*.json")):
        with open(file, encoding="utf-8") as f:
            links.extend(json.load(f))

    return institutions, nodes, links


def link_sort_key(link):
    return (link["a"], link["b"], tuple(link["owners"]))


def build_manager(name, primary_owner_id, institutions, nodes, node_names, links):
    """
    Build a GRENMLManager containing only the given nodes and links,
    plus every institution (so co-ownership references stay valid).
    """
    manager = grenml.GRENMLManager(name)

    institution_ids = {}
    for inst in institutions:
        institution_ids[inst["id"]] = manager.add_institution(
            Institution(name=inst["name"], tag=inst["tag"])
        )

    manager.set_primary_owner(institution_ids[primary_owner_id])

    node_ids = {}
    for node_name in sorted(node_names):
        node = nodes[node_name]
        try:
            node_ids[node_name] = manager.add_nodes([
                Node(
                    name=node["name"],
                    latitude=node["lat"],
                    longitude=node["lon"],
                    owners=[institution_ids[o] for o in node["owners"]],
                    networks=node["networks"]
                )
            ])[0]
        except Exception:
            print("Error adding node:")
            print(json.dumps(node, indent=2, ensure_ascii=False))
            raise

    links_to_add = []
    for link in sorted(links, key=link_sort_key):
        try:
            links_to_add.append(
                Link(
                    name=f"{link['a']} - {link['b']}",
                    nodes=[node_ids[link["a"]], node_ids[link["b"]]],
                    owners=[institution_ids[o] for o in link["owners"]],
                    networks=link["networks"]
                )
            )
        except Exception:
            print("Error adding link:")
            print(json.dumps(link, indent=2, ensure_ascii=False))
            raise
    manager.add_links(links_to_add)

    return manager


def generate(output_dir=RENMAP_DIR, data_dir=DATA_DIR):
    institutions, nodes, links = load_data(data_dir)
    output_dir = Path(output_dir)

    # -------------------------
    # COMBINED TOPOLOGY (every network together)
    # -------------------------
    combined = build_manager(
        COMBINED_NAME, COMBINED_OWNER, institutions, nodes, nodes.keys(), links
    )
    combined.write_to_file(str(output_dir / "topologies.xml"))

    # -------------------------
    # PER-NETWORK TOPOLOGIES
    # -------------------------
    per_network_dir = output_dir / "topologies"
    # Start from scratch so networks removed from the data don't leave
    # stale files behind.
    if per_network_dir.exists():
        shutil.rmtree(per_network_dir)

    for inst in institutions:
        owner_id = inst["id"]
        owner_links = [link for link in links if owner_id in link["owners"]]
        if not owner_links:
            # No links owned by this institution: nothing to publish
            # as a standalone network.
            continue

        needed_node_names = {
            name for link in owner_links for name in (link["a"], link["b"])
        }
        needed_node_names |= {
            name for name, node in nodes.items() if owner_id in node["owners"]
        }

        network = build_manager(
            inst["name"], owner_id, institutions, nodes, needed_node_names, owner_links
        )

        tag_dir = per_network_dir / inst["tag"]
        tag_dir.mkdir(parents=True, exist_ok=True)
        network.write_to_file(str(tag_dir / f"{owner_id}.xml"))


def main():
    # The grenml library keeps elements in sets, so the XML element order
    # follows string hashing. Pin the hash seed (it can only be set before
    # the interpreter starts) so identical data always yields identical
    # bytes; the map server relies on that to detect changes.
    if os.environ.get("PYTHONHASHSEED") != "0":
        env = dict(os.environ, PYTHONHASHSEED="0")
        os.execve(sys.executable, [sys.executable, *sys.argv], env)

    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "--output-dir", default=RENMAP_DIR, type=Path,
        help="where to write topologies.xml and topologies/ (default: RENMAP/)",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generate(args.output_dir)


if __name__ == "__main__":
    main()
