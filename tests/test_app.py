"""The demo page, run with tiny untrained models (see test_models.py).

Skipped where streamlit or sentence-transformers is not installed, as on the
GitHub test machines.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("sentence_transformers")

from streamlit.testing.v1 import AppTest  # noqa: E402
from test_models import TEXTS, build_tiny_models  # noqa: E402

from rulecite.records import Rule, save_rules  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "rulecite" / "app.py")


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    folder = tmp_path_factory.mktemp("app")
    encoder, cross = build_tiny_models(folder)
    rules = [Rule(id=f"DISP 1.{i}.1", type="R", book="DISP", kind="rule", chapter="DISP 1",
                  section=f"DISP 1.{i}", section_title="Title", text=t)
             for i, t in enumerate(TEXTS, 1)]
    save_rules(rules, folder / "rules.jsonl")
    return {"RULECITE_RULES": str(folder / "rules.jsonl"), "RULECITE_DENSE_MODEL": encoder,
            "RULECITE_RERANKER": cross, "RULECITE_CACHE": str(folder / "cache")}


@pytest.fixture
def app(env, monkeypatch):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    return at


def test_page_loads_with_examples(app):
    assert app.title[0].value == "rulecite"
    assert len(app.button) == 5


def test_answer_with_a_low_threshold(app):
    app.sidebar.slider[0].set_value(-8.0).run()
    app.text_input[0].input("How long to cancel a contract?").run()
    assert not app.exception
    assert app.subheader[0].value.startswith("Answer: DISP 1.")


def test_refuses_with_a_high_threshold(app):
    app.sidebar.slider[0].set_value(8.0).run()
    app.button[4].click().run()
    assert not app.exception
    assert "clearly answers" in app.warning[0].value


def test_missing_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("RULECITE_RULES", str(tmp_path / "none.jsonl"))
    at = AppTest.from_file(APP).run()
    assert "make ingest" in at.error[0].value
