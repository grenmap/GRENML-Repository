# GRENML Repository

GRENML topologies of research and education networks. The `RENMAP/` folder is the
source of truth for the map at [renmap.rnp.br](https://renmap.rnp.br/): anyone can
propose a correction with a pull request, and once it is merged the map picks it up
automatically.

## How a correction reaches the map

1. **Propose:** edit the JSON files in `RENMAP/data/` and open a pull request.
2. **Automatic check:** the *Validate topology* workflow checks the data, generates
   the GRENML and posts a summary of what changed (nodes and links added, removed or
   moved) on the workflow run page. The generated XML is attached as an artifact.
3. **Review:** a maintainer reviews and merges the pull request.
4. **Publish:** on `main`, the *Publish GRENML* workflow regenerates
   `RENMAP/topologies.xml` and `RENMAP/topologies/` and commits them.
5. **Map update:** the renmap.rnp.br server checks `RENMAP/topologies.xml` every
   10 minutes and imports it when it changes. Institution popup texts are kept.

You only ever edit files under `RENMAP/data/`. The XML files are generated, so
don't edit them by hand: the next publish overwrites them.

## Data format

```
RENMAP/data/
  institutions.json   every institution (network operator)
  nodes/<id>.json     the nodes of one network
  links/<id>.json     the links of one network
```

File names are just a way to organise the data; what ties nodes and links to an
institution is the `owners` field.

### `institutions.json`

```json
[
  { "id": "rnp", "name": "RNP", "tag": "nren" }
]
```

| Field  | Description |
| ------ | ----------- |
| `id`   | Short identifier used in `owners`. Unique. |
| `name` | Name shown on the map. Unique. |
| `tag`  | `nren` (national network) or `pren` (regional/international network). |

> **Renaming an institution resets its map popup.** The GRENML ID is derived from
> the name, so the server treats a renamed institution as a new one. After the
> rename is published, the popup text has to be entered again in the map's admin.

### `nodes/<id>.json`

```json
[
  { "name": "Boa Vista", "lat": 2.82, "lon": -60.67, "owners": ["rnp"], "networks": "RNP" }
]
```

| Field      | Description |
| ---------- | ----------- |
| `name`     | Node name, unique across **all** node files (links refer to nodes by name). |
| `lat`      | Latitude in decimal degrees, −90 to 90. Not exactly `0` (use e.g. `0.0001`). |
| `lon`      | Longitude in decimal degrees, −180 to 180. Not exactly `0` (use e.g. `0.0001`). |
| `owners`   | List of institution `id`s. |
| `networks` | Network name(s) shown for the node. |

### `links/<id>.json`

```json
[
  { "a": "Boa Vista", "b": "Manaus", "owners": ["rnp"], "networks": "RNP" }
]
```

| Field      | Description |
| ---------- | ----------- |
| `a`, `b`   | Names of the two nodes the link connects. |
| `owners`   | List of institution `id`s. |
| `networks` | Network name(s) shown for the link. |

The same link written twice in the same direction is an error. The same pair in
opposite directions (`a`→`b` and `b`→`a`) is accepted as a parallel circuit but
reported as a warning.

## Running the checks locally

Optional: the pull request workflow runs the same checks. You need
[uv](https://docs.astral.sh/uv/).

```sh
uv run --project RENMAP RENMAP/scripts/validate.py   # check the data
uv run --project RENMAP RENMAP/scripts/generate.py --output-dir /tmp/grenml   # generate the XML
```

The generator is deterministic: the same data always produces byte-identical XML.

## Other folders

`NRENs/` and the `[POC]` files are earlier hand-made topologies. They are not part
of the automated flow.
