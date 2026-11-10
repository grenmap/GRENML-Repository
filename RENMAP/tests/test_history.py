import json
import subprocess

import pytest

from conftest import write_data
from history import last_changes


def run_git(repo, *args, date=None):
    env = None
    if date:
        stamp = f"{date}T12:00:00+00:00"
        env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp, "PATH": "/usr/bin:/bin"}
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.org",
         "-c", "commit.gpgsign=false", *args],
        cwd=repo, env=env, check=True, capture_output=True, text=True,
    ).stdout


def commit(repo, message, date):
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "--allow-empty", "-m", message, date=date)
    return run_git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path):
    run_git(tmp_path, "init", "-q", "-b", "main")
    return tmp_path


@pytest.fixture
def data_dir(repo):
    return repo / "RENMAP" / "data"


def test_dates_follow_each_networks_own_changes(repo, data_dir, sample):
    institutions, nodes, links = sample
    write_data(data_dir, institutions, nodes, links)
    first = commit(repo, "initial data", "2026-01-10")
    assert last_changes(repo) == {"redclara": ("2026-01-10", first), "rnp": ("2026-01-10", first)}

    # Moving a RedCLARA node only touches RedCLARA.
    nodes[2]["lat"] = 9.0
    write_data(data_dir, institutions, nodes, links)
    moved = commit(repo, "move Panama", "2026-02-01")
    assert last_changes(repo) == {"redclara": ("2026-02-01", moved), "rnp": ("2026-01-10", first)}

    # A node RNP owns counts for RNP even in another network's file.
    (data_dir / "nodes" / "redclara.json").write_text(json.dumps([
        {"name": "Belem", "lat": -1.45, "lon": -48.5, "owners": ["rnp"], "networks": "RNP"},
    ]))
    co_owned = commit(repo, "add Belem in redclara.json", "2026-03-01")
    assert last_changes(repo)["rnp"] == ("2026-03-01", co_owned)
    assert last_changes(repo)["redclara"] == ("2026-02-01", moved)

    # Scripts and generated XML are not data.
    (repo / "RENMAP" / "scripts").mkdir()
    (repo / "RENMAP" / "scripts" / "x.py").write_text("print()\n")
    (repo / "RENMAP" / "topologies.xml").write_text("<xml/>\n")
    commit(repo, "regenerate", "2026-04-01")
    assert last_changes(repo)["rnp"] == ("2026-03-01", co_owned)

    # Removing a link is a change for its owner.
    del links[1]
    write_data(data_dir, institutions, nodes, links)
    removed = commit(repo, "drop Manaus - Panama", "2026-05-01")
    assert last_changes(repo)["redclara"] == ("2026-05-01", removed)

    # Changing the institution entry itself (e.g. verifying it) counts too.
    institutions[1].update(verified_by="hugoromao", verified_on="2026-05-02")
    write_data(data_dir, institutions, nodes, links)
    verified = commit(repo, "verify RNP", "2026-05-02")
    assert last_changes(repo)["rnp"] == ("2026-05-02", verified)


def test_merged_pull_request_is_dated_by_its_merge(repo, data_dir, sample):
    institutions, nodes, links = sample
    write_data(data_dir, institutions, nodes, links)
    commit(repo, "initial data", "2026-01-10")

    run_git(repo, "checkout", "-q", "-b", "fix-boa-vista")
    nodes[0]["lon"] = -60.7
    write_data(data_dir, institutions, nodes, links)
    commit(repo, "fix Boa Vista", "2026-05-20")
    run_git(repo, "checkout", "-q", "main")
    run_git(repo, "merge", "-q", "--no-ff", "-m", "Merge pull request #9", "fix-boa-vista", date="2026-06-01")
    merge = run_git(repo, "rev-parse", "HEAD").strip()

    assert last_changes(repo)["rnp"] == ("2026-06-01", merge)


def test_commit_with_unreadable_data_is_skipped(repo, data_dir, sample):
    institutions, nodes, links = sample
    write_data(data_dir, institutions, nodes, links)
    first = commit(repo, "initial data", "2026-01-10")
    (data_dir / "nodes" / "all.json").write_text("[ broken")
    commit(repo, "broken", "2026-02-01")
    write_data(data_dir, institutions, nodes, links)
    commit(repo, "fixed, same data as before", "2026-02-02")

    assert last_changes(repo)["rnp"] == ("2026-01-10", first)


def test_no_history_without_git(tmp_path):
    assert last_changes(tmp_path) is None


def test_no_history_in_a_shallow_clone(repo, data_dir, sample, tmp_path_factory):
    write_data(data_dir, *sample)
    commit(repo, "one", "2026-01-10")
    commit(repo, "two", "2026-01-11")
    clone = tmp_path_factory.mktemp("clone") / "shallow"
    run_git(repo, "clone", "-q", "--depth", "1", f"file://{repo}", str(clone))

    assert last_changes(clone) is None
