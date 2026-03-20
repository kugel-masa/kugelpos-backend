"""Unit tests for app/services/report_plugin_manager.py"""
import json
import pytest
from unittest.mock import patch, mock_open, MagicMock


SAMPLE_CONFIG = {
    "report": {
        "daily_sales": {
            "module": "app.services.plugins.daily_sales_plugin",
            "class": "DailySalesPlugin",
            "args": ["<db>", "<tenant_code>"],
            "kwargs": {"verbose": True},
        },
        "summary": {
            "module": "app.services.plugins.summary_plugin",
            "function": "generate_summary",
        },
    }
}


@patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_CONFIG)))
def test_init_loads_config():
    """__init__ should open plugins.json and parse it."""
    from app.services.report_plugin_manager import ReportPluginManager

    mgr = ReportPluginManager()
    assert mgr.config == SAMPLE_CONFIG
    assert mgr.config_path == "app/services/plugins/plugins.json"


@patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_CONFIG)))
def test_load_plugins_class_based():
    """load_plugins should instantiate class-based plugins with substituted args."""
    from app.services.report_plugin_manager import ReportPluginManager

    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.DailySalesPlugin = mock_class

    # For the function-based entry, provide a callable
    mock_func = MagicMock()
    mock_module.generate_summary = mock_func

    mgr = ReportPluginManager()

    with patch("importlib.import_module") as mock_import:
        # Return different modules for different module names
        def side_effect(name):
            return mock_module

        mock_import.side_effect = side_effect

        fake_db = MagicMock()
        plugins = mgr.load_plugins("report", db=fake_db, tenant_code="T001")

    # Class-based plugin should be instantiated with substituted args and kwargs
    mock_class.assert_called_once_with(fake_db, "T001", verbose=True)
    assert "daily_sales" in plugins

    # Function-based plugin should be the function itself
    assert plugins["summary"] is mock_func


@patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_CONFIG)))
def test_load_plugins_function_based():
    """load_plugins should store function references for function-based plugins."""
    from app.services.report_plugin_manager import ReportPluginManager

    mock_func = MagicMock()
    mock_module = MagicMock()
    mock_module.generate_summary = mock_func

    # Only include the function-based plugin in config
    func_only_config = {
        "report": {
            "summary": {
                "module": "app.services.plugins.summary_plugin",
                "function": "generate_summary",
            }
        }
    }

    mgr = ReportPluginManager()
    mgr.config = func_only_config

    with patch("importlib.import_module", return_value=mock_module):
        plugins = mgr.load_plugins("report")

    assert plugins["summary"] is mock_func


@patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_CONFIG)))
def test_load_plugins_args_no_substitution():
    """Args that are not <placeholder> should be passed as-is."""
    from app.services.report_plugin_manager import ReportPluginManager

    config_literal_args = {
        "report": {
            "fixed": {
                "module": "some.module",
                "class": "FixedPlugin",
                "args": ["literal_value", "<db>"],
            }
        }
    }

    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.FixedPlugin = mock_class

    mgr = ReportPluginManager()
    mgr.config = config_literal_args

    fake_db = MagicMock()
    with patch("importlib.import_module", return_value=mock_module):
        mgr.load_plugins("report", db=fake_db)

    # "literal_value" is not a <placeholder>, so kwargs.get returns "literal_value" itself
    mock_class.assert_called_once_with("literal_value", fake_db)


@patch("builtins.open", mock_open(read_data=json.dumps(SAMPLE_CONFIG)))
def test_load_plugins_class_no_args_no_kwargs():
    """Class-based plugin with no args/kwargs should be instantiated with no arguments."""
    from app.services.report_plugin_manager import ReportPluginManager

    config_no_args = {
        "report": {
            "simple": {
                "module": "some.module",
                "class": "SimplePlugin",
            }
        }
    }

    mock_class = MagicMock()
    mock_module = MagicMock()
    mock_module.SimplePlugin = mock_class

    mgr = ReportPluginManager()
    mgr.config = config_no_args

    with patch("importlib.import_module", return_value=mock_module):
        plugins = mgr.load_plugins("report")

    mock_class.assert_called_once_with()
    assert "simple" in plugins
