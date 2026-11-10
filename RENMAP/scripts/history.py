"""
When each network's data last changed, worked out from the repository's
git history, so nobody has to keep a date up to date by hand.

A network's data is its entry in institutions.json plus every node and
link it owns (its id in "owners"), whichever file they are in. Walking
main's first-parent history (one step per merged pull request or direct
push), the last commit in which that data differed from the step before
is the network's last change.
"""
import json
import subprocess
from datetime import datetime, timezone

REPOSITORY_URL = "https://github.com/grenmap/GRENML-Repository"


def git(repo_root, *args, input=None):
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        input=input, capture_output=True, text=True, check=True,
    ).stdout


def read_files(repo_root, rev, paths):
    """Contents of the given paths at rev, read with one git process."""
    if not paths:
        return {}
    out = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "--batch"],
        input="".join(f"{rev}:{path}\n" for path in paths).encode(),
        capture_output=True, check=True,
    ).stdout
    contents = {}
    pos = 0
    for path in paths:
        header_end = out.index(b"\n", pos)
        size = int(out[pos:header_end].split()[2])
        start = header_end + 1
        contents[path] = out[start:start + size].decode("utf-8")
        pos = start + size + 1  # content is followed by a newline
    return contents


def load_data_at(repo_root, rev, data_path):
    """institutions, nodes and links as they were at rev (like generate.load_data)."""
    paths = [
        p for p in git(repo_root, "ls-tree", "-r", "--name-only", rev, "--", data_path).splitlines()
        if p.endswith(".json")
    ]
    contents = read_files(repo_root, rev, paths)
    institutions, nodes, links = [], [], []
    for path, text in contents.items():
        relative = path[len(data_path) + 1:]
        if relative == "institutions.json":
            institutions = json.loads(text)
        elif relative.startswith("nodes/"):
            nodes.extend(json.loads(text))
        elif relative.startswith("links/"):
            links.extend(json.loads(text))
    return institutions, nodes, links


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def fingerprints(institutions, nodes, links):
    """One comparable string per institution id covering everything it owns."""
    owned = {
        inst["id"]: {"institution": inst, "nodes": [], "links": []}
        for inst in institutions
    }
    for kind, elements in (("nodes", nodes), ("links", links)):
        for element in elements:
            for owner in element.get("owners", []):
                if owner in owned:
                    owned[owner][kind].append(canonical(element))
    return {
        inst_id: canonical({**data, "nodes": sorted(data["nodes"]), "links": sorted(data["links"])})
        for inst_id, data in owned.items()
    }


def last_changes(repo_root, data_path="RENMAP/data", rev="HEAD"):
    """
    {institution id: (YYYY-MM-DD in UTC, commit sha)} of each network's
    last change up to rev, or None when there is no usable history (not
    a git checkout, or a shallow clone that would date everything to
    its single commit).
    """
    try:
        if git(repo_root, "rev-parse", "--is-shallow-repository").strip() == "true":
            return None
        log = git(repo_root, "log", "--first-parent", "--reverse", "--format=%H %ct", rev, "--", data_path)
    except (OSError, subprocess.CalledProcessError):
        return None

    changes = {}
    previous = {}
    for line in log.splitlines():
        sha, timestamp = line.split()
        try:
            current = fingerprints(*load_data_at(repo_root, sha, data_path))
        except (ValueError, KeyError, TypeError, AttributeError, subprocess.CalledProcessError):
            # Data that didn't load at this commit (invalid JSON, a
            # missing field): skip it; the next commit is compared with
            # the last one that loaded.
            continue
        day = datetime.fromtimestamp(int(timestamp), timezone.utc).date().isoformat()
        for inst_id, fingerprint in current.items():
            if previous.get(inst_id) != fingerprint:
                changes[inst_id] = (day, sha)
        previous = current
    return changes


def commit_url(sha):
    return f"{REPOSITORY_URL}/commit/{sha}"
