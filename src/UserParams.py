import ast
from pathlib import Path

from AppPaths import resource_root

# Running from source, params/ lives at the repo root (one level up from
# src/). Frozen, it's bundled alongside the app instead - see AppPaths.py.
PARAMS_DIR = resource_root() / "params"
FILENAME_PREFIX = "UserParams_"
FILENAME_SUFFIX = ".txt"

DEFAULT_VERSION = "AP3-SUB-006"

_FIELD_NAMES = ("throttleField", "plotNames", "plotFields", "plotLimits", "plotSpecs")


class UserParams:
    """Per-AccessPort-version plot configuration, read from
    params/UserParams_<version>.txt.

    Schema: a flat set of top-level `name = <python literal>` assignments
    (str/list/dict/tuple/number/bool - the same shapes this module used to
    hardcode directly). Files are parsed with ast.literal_eval, never
    exec'd/imported, so hand-editing them can't run arbitrary code.
    """

    def __init__(self, params_dir=None):
        self.params_dir = Path(params_dir) if params_dir else PARAMS_DIR
        self.version = None
        self.throttleField = ""
        self.plotNames = []
        self.plotFields = {}
        self.plotLimits = {}
        self.plotSpecs = {}

    def params_path(self, version):
        return self.params_dir / f"{FILENAME_PREFIX}{version}{FILENAME_SUFFIX}"

    def available_versions(self):
        """Versions supported by whatever UserParams_*.txt files currently
        exist in params/ - read fresh each call so a file dropped in (or
        removed) shows up without restarting the app."""
        if not self.params_dir.is_dir():
            return []
        versions = [
            path.stem[len(FILENAME_PREFIX):]
            for path in self.params_dir.glob(f"{FILENAME_PREFIX}*{FILENAME_SUFFIX}")
        ]
        return sorted(versions)

    def read_params(self, version):
        """(Re)populate every field from params/UserParams_<version>.txt."""
        values = self._parse_text(self.params_path(version).read_text(encoding="utf-8"))
        self.throttleField = values.get("throttleField", "")
        self.plotNames = values.get("plotNames", [])
        self.plotFields = values.get("plotFields", {})
        self.plotLimits = values.get("plotLimits", {})
        self.plotSpecs = values.get("plotSpecs", {})
        self.version = version

    def read_raw(self, version=None):
        """Raw file text, for a user-editable view of the params."""
        return self.params_path(version or self.version).read_text(encoding="utf-8")

    def write_raw(self, text, version=None):
        """Validate `text` parses under the same schema as read_params, then
        write it to that version's file. Reloads this instance's fields from
        it if it's the currently active version."""
        version = version or self.version
        self._parse_text(text)  # raises on invalid input before touching the file
        self.params_path(version).write_text(text, encoding="utf-8")
        if version == self.version:
            self.read_params(version)

    @staticmethod
    def _parse_text(text):
        tree = ast.parse(text)
        values = {}
        for node in tree.body:
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in _FIELD_NAMES):
                values[node.targets[0].id] = ast.literal_eval(node.value)
        return values
