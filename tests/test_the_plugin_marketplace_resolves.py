"""The plugin marketplace at `.claude-plugin/marketplace.json` resolves to plugins that exist.

WHAT THIS EXISTS FOR. `claude plugin validate` and `claude plugin test` are the real checks on a
plugin, and CI cannot run either: neither `gates` runner has the `claude` CLI. So this file pins the
part CI can read without it. The marketplace parses, every listed plugin's `source` is a folder in
this tree, that folder's own `plugin.json` carries the name the marketplace lists, its hooks modules
exist, and every file in both places is ASCII.

THE FAILURE IT PINS. A rename that moves the folder, or edits one name and not the other, leaves
`/plugin install korus-fleet@korus` failing for every reader who copies this repository. Nothing
else in the suite opens these files.

ONE MORE PIN, ON A CLAIM THE DOCS MAKE. `docs/PLUGINS.md` says the plugin is read-only. A source
that calls `$.fs.write` breaks that claim, so the checker refuses one.

ARTICLE V. The checker is a function so a planted control can reach it. It runs over three trees:
the live one, which must come back clean having read at least one plugin, a planted clean copy,
and a planted broken one, which must fire once per defect planted. A checker that returns nothing
on the broken tree is broken, and the live zero means nothing without it. This is the pairing
`test_every_validation_check_is_proven_by_a_control.py` requires of `scripts/validation/`.

Run: python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

import _ccxtest as t

MARKETPLACE = Path(".claude-plugin") / "marketplace.json"
#: A call, not a mention: a comment naming the API is not a write.
FS_WRITE_CALL = re.compile(r"\$\.fs\.write\s*\(")
SOURCE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")


def _non_ascii(path: Path) -> str | None:
    data = path.read_bytes()
    for offset, byte in enumerate(data):
        if byte > 0x7F:
            return f"{path.as_posix()}: non-ASCII byte 0x{byte:02X} at offset {offset}"
    return None


def problems(root: Path) -> tuple[list[str], int]:
    """Every defect in the marketplace under `root`, and how many plugins it read.

    The count is returned so a caller can tell a clean marketplace from one that listed nothing.
    """
    found: list[str] = []
    manifest = root / MARKETPLACE
    if not manifest.is_file():
        return [f"{MARKETPLACE.as_posix()} is missing"], 0
    try:
        market = json.loads(manifest.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        return [f"{MARKETPLACE.as_posix()} does not parse: {err}"], 0
    if not isinstance(market, dict):
        return [f"{MARKETPLACE.as_posix()} is not a JSON object"], 0
    if not isinstance(market.get("name"), str) or not market["name"]:
        found.append("marketplace has no name")
    plugins = market.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        return found + ["marketplace lists no plugins"], 0

    scanned: list[Path] = [manifest]
    read = 0
    for entry in plugins:
        if not isinstance(entry, dict):
            found.append(f"plugin entry is not an object: {entry!r}")
            continue
        name = entry.get("name")
        source = entry.get("source")
        if not isinstance(name, str) or not name:
            found.append(f"plugin entry has no name: {entry!r}")
            continue
        if not isinstance(source, str) or not source.startswith("./"):
            found.append(f"{name}: source must be a './' path in this tree, got {source!r}")
            continue
        folder = (root / source).resolve()
        if not folder.is_relative_to(root.resolve()):
            found.append(f"{name}: source {source} leaves the repository")
            continue
        if not folder.is_dir():
            found.append(f"{name}: source {source} does not exist")
            continue
        read += 1
        plugin_json = folder / ".claude-plugin" / "plugin.json"
        if not plugin_json.is_file():
            found.append(f"{name}: {source}/.claude-plugin/plugin.json is missing")
            continue
        try:
            plugin = json.loads(plugin_json.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            found.append(f"{name}: plugin.json does not parse: {err}")
            continue
        if not isinstance(plugin, dict) or plugin.get("name") != name:
            listed = plugin.get("name") if isinstance(plugin, dict) else None
            found.append(f"{name}: plugin.json names itself {listed!r}")
        hooks_json = folder / "hooks" / "hooks.json"
        if hooks_json.is_file():
            try:
                modules = json.loads(hooks_json.read_text(encoding="utf-8")).get("modules", [])
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as err:
                found.append(f"{name}: hooks/hooks.json does not parse: {err}")
                modules = []
            for module in modules:
                if not (hooks_json.parent / module).is_file():
                    found.append(f"{name}: hooks module {module} does not exist")
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or "node_modules" in path.parts:
                continue
            # The editor types `/plugin-types` writes are generated and git-ignored.
            if ".claude-plugin" in path.parts and "types" in path.parts:
                continue
            scanned.append(path)
            if path.suffix in SOURCE_SUFFIXES and FS_WRITE_CALL.search(
                path.read_text(encoding="utf-8", errors="replace")
            ):
                found.append(f"{name}: {path.name} calls $.fs.write; the plugin is documented read-only")
    for path in scanned:
        bad = _non_ascii(path)
        if bad is not None:
            found.append(bad.replace(root.as_posix() + "/", ""))
    return found, read


def _plant(root: Path, *, name_in_plugin: str, register: str, extra_entry: bool) -> None:
    (root / ".claude-plugin").mkdir(parents=True)
    entries = [{"name": "demo", "source": "./plugins/demo"}]
    if extra_entry:
        entries.append({"name": "ghost", "source": "./plugins/ghost"})
    (root / MARKETPLACE).write_text(json.dumps({"name": "m", "plugins": entries}), encoding="ascii")
    plugin = root / "plugins" / "demo"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / "hooks").mkdir()
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": name_in_plugin}), encoding="ascii"
    )
    (plugin / "hooks" / "hooks.json").write_text('{"modules": ["./register.tsx"]}', encoding="ascii")
    (plugin / "hooks" / "register.tsx").write_text(register, encoding="utf-8")


class TheMarketplaceResolves(unittest.TestCase):
    def test_the_live_marketplace_is_clean_and_read_something(self):
        found, read = problems(t.REPO_ROOT)
        self.assertEqual(found, [], "the marketplace does not resolve:\n  " + "\n  ".join(found))
        self.assertGreaterEqual(
            read, 1, "the checker read no plugin, so its clean result above measures nothing."
        )

    def test_a_planted_clean_marketplace_comes_back_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(root, name_in_plugin="demo", register="export const register = () => {}\n",
                   extra_entry=False)
            self.assertEqual(problems(root), ([], 1))

    def test_each_planted_defect_fires(self):
        """Four defects planted, four findings required, each named by what it is."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _plant(
                root,
                name_in_plugin="demo-renamed",
                register="// caf" + chr(0xE9) + "\nexport const register = on => { void $.fs.write('x', 'y') }\n",
                extra_entry=True,
            )
            found, read = problems(root)
        self.assertEqual(read, 1)
        joined = "\n".join(found)
        self.assertIn("demo: plugin.json names itself 'demo-renamed'", joined)
        self.assertIn("ghost: source ./plugins/ghost does not exist", joined)
        self.assertIn("calls $.fs.write", joined)
        self.assertIn("non-ASCII byte 0xC3", joined)
        self.assertEqual(len(found), 4, joined)

    def test_a_marketplace_that_does_not_parse_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude-plugin").mkdir()
            (root / MARKETPLACE).write_text("{ not json", encoding="ascii")
            found, read = problems(root)
        self.assertEqual(read, 0)
        self.assertEqual(len(found), 1)
        self.assertIn("does not parse", found[0])


class TheFleetScriptDefaultIsStatedOnce(unittest.TestCase):
    """The manifest default and the module's fallback must name the same path.

    The module repeats the default so a load with no options still has a path. Two copies of one
    value drift, and the drift is silent: the pane would run one script while `/config` shows
    another.
    """

    def test_the_manifest_default_matches_the_module_fallback(self):
        plugin = t.REPO_ROOT / "plugins" / "korus-fleet"
        manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        default = manifest["userConfig"]["fleetScript"]["default"]
        source = (plugin / "hooks" / "register.tsx").read_text(encoding="utf-8")
        self.assertIn(f"const DEFAULT_FLEET_SCRIPT = '{default}'", source)


if __name__ == "__main__":
    unittest.main()
