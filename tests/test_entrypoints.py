from pathlib import Path


def test_entrypoint_scripts_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "run_build_index.py").exists()
    assert (root / "run_qa_cli.py").exists()
    assert (root / "run_admin_gui.py").exists()
    assert (root / "run_eval_golden.py").exists()
    assert (root / "run_pilot_isa230.py").exists()
