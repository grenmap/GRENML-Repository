from grenml.parse import GRENMLParser

from conftest import write_data
from generate import generate


def institution_properties(xml_file):
    topology = GRENMLParser().parse_file(str(xml_file)).topology
    return {
        inst.name: {key: values[0] for key, values in inst.additional_properties.items()}
        for inst in topology.institutions
    }


def test_trust_and_update_properties(tmp_path, sample):
    institutions, nodes, links = sample
    institutions[1].update(verified_by="hugoromao", verified_on="2026-11-03")
    data_dir = tmp_path / "data"
    write_data(data_dir, institutions, nodes, links)
    changes = {"rnp": ("2026-11-05", "abc123")}

    (tmp_path / "out").mkdir()
    generate(tmp_path / "out", data_dir, changes)

    for xml_file in (tmp_path / "out" / "topologies.xml", tmp_path / "out" / "topologies" / "nren" / "rnp.xml"):
        properties = institution_properties(xml_file)
        assert properties["RNP"] == {
            "tag": "nren",
            "trust_level": "verified",
            "verified_by": "hugoromao",
            "verified_on": "2026-11-03",
            "data_updated_on": "2026-11-05",
            "data_updated_url": "https://github.com/grenmap/GRENML-Repository/commit/abc123",
        }
        assert properties["RedCLARA"] == {"tag": "pren", "trust_level": "ai_generated"}


def test_without_history_there_are_no_dates(tmp_path, sample):
    data_dir = tmp_path / "data"
    write_data(data_dir, *sample)

    (tmp_path / "out").mkdir()
    generate(tmp_path / "out", data_dir, changes=None)

    properties = institution_properties(tmp_path / "out" / "topologies.xml")
    assert "data_updated_on" not in properties["RNP"]
