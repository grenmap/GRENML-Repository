import json
import sys
from pathlib import Path

import pytest

# The scripts are run directly (not installed), so import them the same way.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def write_data(data_dir, institutions, nodes, links):
    """Lay out a RENMAP/data-style directory: one nodes and one links file."""
    (data_dir / "nodes").mkdir(parents=True, exist_ok=True)
    (data_dir / "links").mkdir(parents=True, exist_ok=True)
    (data_dir / "institutions.json").write_text(json.dumps(institutions, indent=2))
    (data_dir / "nodes" / "all.json").write_text(json.dumps(nodes, indent=2))
    (data_dir / "links" / "all.json").write_text(json.dumps(links, indent=2))


@pytest.fixture
def sample():
    """Minimal consistent data: two networks, three nodes, two links."""
    institutions = [
        {"id": "redclara", "name": "RedCLARA", "tag": "pren"},
        {"id": "rnp", "name": "RNP", "tag": "nren"},
    ]
    nodes = [
        {"name": "Boa Vista", "lat": 2.82, "lon": -60.67, "owners": ["rnp"], "networks": "RNP"},
        {"name": "Manaus", "lat": -3.1, "lon": -60.02, "owners": ["rnp"], "networks": "RNP"},
        {"name": "Panama", "lat": 8.98, "lon": -79.52, "owners": ["redclara"], "networks": "RedCLARA"},
    ]
    links = [
        {"a": "Boa Vista", "b": "Manaus", "owners": ["rnp"], "networks": "RNP"},
        {"a": "Manaus", "b": "Panama", "owners": ["redclara"], "networks": "RedCLARA"},
    ]
    return institutions, nodes, links
