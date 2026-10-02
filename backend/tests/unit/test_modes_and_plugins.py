"""Tests for application modes and the plugin registry."""
import pytest

from backend.app.plugins import PLUGIN_KINDS, discover_plugins, get_registry
from backend.app.research import modes


@pytest.fixture(autouse=True)
def restore_mode():
    yield
    modes.set_mode("research")


# ── Modes (item 21) ──────────────────────────────────────────────────────────

def test_default_mode_is_research():
    assert modes.get_mode() == "research"
    state = modes.mode_state()
    assert state["read_only"] is False
    assert "benchmark" in state["scope"]


def test_demo_mode_switch_and_scope():
    modes.set_mode("demo")
    state = modes.mode_state()
    assert state["mode"] == "demo"
    assert state["read_only"] is True
    assert set(state["scope"]) == {"datasets", "predictions", "explainability", "audit"}


def test_demo_mode_blocks_mutating_endpoints():
    modes.set_mode("demo")
    assert modes.endpoint_allowed("GET", "/api/v1/datasets") is True
    assert modes.endpoint_allowed("POST", "/api/v1/datasets") is False
    assert modes.endpoint_allowed("POST", "/api/v1/models/train") is False
    assert modes.endpoint_allowed("POST", "/api/v1/experiments/EXP-A/run") is False
    # golden path stays open: prediction, explanation, verification, export
    assert modes.endpoint_allowed("POST", "/api/v1/predictions") is True
    assert modes.endpoint_allowed("POST", "/api/v1/explanations/p1") is True
    assert modes.endpoint_allowed("POST", "/api/v1/audit/verify") is True
    assert modes.endpoint_allowed("GET", "/api/v1/audit/export") is True


def test_research_mode_allows_everything():
    assert modes.endpoint_allowed("POST", "/api/v1/datasets") is True
    assert modes.endpoint_allowed("DELETE", "/api/v1/models/m1") is True


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="Unknown mode"):
        modes.set_mode("hacker")


# ── Plugins (item 18) ────────────────────────────────────────────────────────

def test_builtin_plugins_registered_across_all_kinds():
    registry = get_registry()
    counts = registry.counts()
    for kind in PLUGIN_KINDS:
        assert counts[kind] >= 1, f"no builtin plugin for kind '{kind}'"


def test_plugin_create_returns_working_component():
    registry = get_registry()
    dataset = registry.create("dataset", "synthetic_flows", n_samples=100)
    assert len(dataset) == 100
    model = registry.create("model", "random_forest")
    assert model.model_type == "random_forest"


def test_plugin_registration_and_retrieval():
    registry = get_registry()
    registry.register("xai", "custom_explainer", lambda: "custom-object",
                      description="test plugin", source="test")
    assert registry.create("xai", "custom_explainer") == "custom-object"


def test_plugin_duplicate_registration_rejected_without_replace():
    registry = get_registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register("dataset", "synthetic_flows", lambda: None)


def test_plugin_unknown_kind_and_name_rejected():
    registry = get_registry()
    with pytest.raises(ValueError, match="Unknown plugin kind"):
        registry.register("quantum", "q1", lambda: None)
    with pytest.raises(ValueError, match="No dataset plugin"):
        registry.create("dataset", "nonexistent")


def test_discover_plugins_from_directory(tmp_path):
    plugin_file = tmp_path / "my_plugin.py"
    plugin_file.write_text(
        "from backend.app.plugins import get_registry\n"
        "get_registry().register('metric', 'from_file', lambda: 42, source='file')\n"
    )
    report = discover_plugins(directory=tmp_path)
    assert report["loaded"] == ["my_plugin.py"]
    assert get_registry().create("metric", "from_file") == 42


def test_discover_plugins_tolerates_broken_file(tmp_path):
    (tmp_path / "broken.py").write_text("raise RuntimeError('boom')\n")
    report = discover_plugins(directory=tmp_path)
    assert report["loaded"] == []
    assert "broken.py" in report["errors"]
