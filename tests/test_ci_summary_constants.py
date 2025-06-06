import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "ci_summary",
    Path(__file__).resolve().parents[1] / "scripts" / "ci_summary.py",
)
assert spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)  # type: ignore


def test_constants_present():
    for name in ("CHECK", "CROSS", "ENCODING"):
        assert hasattr(module, name)
