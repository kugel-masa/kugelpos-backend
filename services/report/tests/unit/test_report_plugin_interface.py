# Copyright 2026 masa@kugel
"""The calling contract and the optional capabilities of IReportPlugin.

generate_report() accepts keyword arguments beyond its parameters. merge() and
from_saved() are optional: a plugin that does not implement them refuses by
name rather than failing obscurely.
"""
import importlib
import inspect
import json
from pathlib import Path

import pytest

from app.services.report_plugin_interface import IReportPlugin


class _Minimal(IReportPlugin):
    async def generate_report(self, *args, **kwargs):
        return {}


class _Combining(_Minimal):
    def merge(self, reports):
        return {"total": sum(r["total"] for r in reports)}

    def from_saved(self, report):
        return dict(report)


def test_a_plugin_needs_only_generate_report():
    _Minimal()


@pytest.mark.parametrize("call", [lambda p: p.merge([{"total": 1}]), lambda p: p.from_saved({"total": 1})])
def test_an_unsupported_hook_refuses_by_name(call):
    with pytest.raises(NotImplementedError, match="^_Minimal: "):
        call(_Minimal())


def test_a_plugin_can_support_the_hooks():
    plugin = _Combining()
    assert plugin.merge([{"total": 1}, {"total": 2}]) == {"total": 3}
    assert plugin.from_saved({"total": 4}) == {"total": 4}


PLUGINS_JSON = Path(__file__).resolve().parents[2] / "app" / "services" / "plugins" / "plugins.json"


def _accepts_any_keyword(method) -> bool:
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in inspect.signature(method).parameters.values())


def test_the_interface_accepts_further_keywords():
    assert _accepts_any_keyword(IReportPlugin.generate_report)


def test_every_configured_report_maker_accepts_further_keywords():
    makers = json.loads(PLUGINS_JSON.read_text())["report_makers"]
    assert makers
    for name, entry in makers.items():
        maker_class = getattr(importlib.import_module(entry["module"]), entry["class"])
        assert issubclass(maker_class, IReportPlugin), name
        assert _accepts_any_keyword(maker_class.generate_report), f"{name} rejects further keywords"
