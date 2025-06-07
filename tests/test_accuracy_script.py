import importlib.util
import shutil
import sys
from decimal import Decimal
from pathlib import Path

import pytest

# add project src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

mod_spec = importlib.util.spec_from_file_location(
    "check_accuracy",
    Path(__file__).resolve().parents[1] / "scripts" / "check_accuracy.py",
)
mod = importlib.util.module_from_spec(mod_spec)
assert mod_spec.loader
mod_spec.loader.exec_module(mod)


@pytest.mark.parametrize("has_pdfplumber", [True, False])
def test_check_accuracy_main_fails_on_mismatch(monkeypatch, tmp_path, has_pdfplumber):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample_pdf = Path(__file__).parent / "data" / "itau_2024-10.pdf"
    sample_txt = Path(__file__).parent / "data" / "itau_2024-10.txt"
    sample_golden = Path(__file__).parent / "data" / "golden_2024-10.csv"
    shutil.copy(sample_pdf, data_dir / sample_pdf.name)
    shutil.copy(sample_txt, data_dir / sample_txt.name)
    broken_golden = data_dir / sample_golden.name
    lines = sample_golden.read_text().splitlines()
    lines[1] = lines[1].replace(".00", ".01")
    broken_golden.write_text("\n".join(lines) + "\n")

    monkeypatch.setattr(mod, "DATA_DIR", data_dir)
    if not has_pdfplumber:
        monkeypatch.setattr(mod, "HAS_PDFPLUMBER", False)
    with pytest.raises(SystemExit):
        mod.main()


def test_check_accuracy_fails_on_total_delta(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sample_pdf = Path(__file__).parent / "data" / "itau_2024-10.pdf"
    sample_txt = Path(__file__).parent / "data" / "itau_2024-10.txt"
    sample_golden = Path(__file__).parent / "data" / "golden_2024-10.csv"
    shutil.copy(sample_pdf, data_dir / sample_pdf.name)
    shutil.copy(sample_txt, data_dir / sample_txt.name)
    shutil.copy(sample_golden, data_dir / sample_golden.name)

    monkeypatch.setattr(mod, "DATA_DIR", data_dir)
    monkeypatch.setattr(mod, "extract_total_from_pdf", lambda _: Decimal("0.00"))
    monkeypatch.setattr(mod, "HAS_PDFPLUMBER", False)
    with pytest.raises(SystemExit):
        mod.main()
