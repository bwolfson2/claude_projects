"""
Tests for the setup wizard (setup_wizard.py).

Verifies:
- Config loading and saving
- Config validation
- Connector status checking
- Default config structure
- Setup summary generation
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from setup_wizard import (
    DEFAULT_CONFIG,
    load_config,
    save_config,
    validate_config,
    check_connector_status,
    get_setup_summary,
)


class TestDefaultConfig:
    """Verify default config structure."""

    def test_has_required_keys(self):
        assert "fund_name" in DEFAULT_CONFIG
        assert "primary_user" in DEFAULT_CONFIG
        assert "primary_email" in DEFAULT_CONFIG
        assert "channels" in DEFAULT_CONFIG
        assert "google_sheet_id" in DEFAULT_CONFIG
        assert "setup_completed" in DEFAULT_CONFIG

    def test_channels_structure(self):
        channels = DEFAULT_CONFIG["channels"]
        assert "email" in channels
        assert "calendar" in channels
        assert "slack" in channels
        assert "whatsapp" in channels
        assert "signal" in channels
        assert "granola" in channels

    def test_default_email_provider(self):
        assert DEFAULT_CONFIG["channels"]["email"]["provider"] == "outlook"

    def test_default_calendar_provider(self):
        assert DEFAULT_CONFIG["channels"]["calendar"]["provider"] == "google"

    def test_whatsapp_disabled_by_default(self):
        assert DEFAULT_CONFIG["channels"]["whatsapp"]["enabled"] is False

    def test_signal_disabled_by_default(self):
        assert DEFAULT_CONFIG["channels"]["signal"]["enabled"] is False


class TestLoadConfig:
    """Test config loading from file."""

    def test_returns_defaults_when_no_file(self, tmp_path):
        with patch("setup_wizard.CONFIG_PATH", tmp_path / "nonexistent.json"):
            config = load_config()
        assert config["setup_completed"] is False
        assert config["fund_name"] == ""

    def test_loads_existing_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({
            "fund_name": "TestFund",
            "primary_email": "test@fund.com",
            "setup_completed": True,
        }))
        with patch("setup_wizard.CONFIG_PATH", config_file):
            config = load_config()
        assert config["fund_name"] == "TestFund"
        assert config["setup_completed"] is True

    def test_handles_corrupt_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("not valid json{{{")
        with patch("setup_wizard.CONFIG_PATH", config_file):
            config = load_config()
        # Should return defaults
        assert config["setup_completed"] is False


class TestSaveConfig:
    """Test config saving."""

    def test_writes_valid_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        config = DEFAULT_CONFIG.copy()
        config["fund_name"] = "SaveTest"
        with patch("setup_wizard.CONFIG_PATH", config_file):
            save_config(config)
        saved = json.loads(config_file.read_text())
        assert saved["fund_name"] == "SaveTest"
        assert saved["setup_completed"] is True
        assert saved["setup_date"] is not None

    def test_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "nested" / "dir" / "config.json"
        config = DEFAULT_CONFIG.copy()
        with patch("setup_wizard.CONFIG_PATH", config_file):
            save_config(config)
        assert config_file.exists()

    def test_sets_setup_completed(self, tmp_path):
        config_file = tmp_path / "config.json"
        config = DEFAULT_CONFIG.copy()
        assert config["setup_completed"] is False
        with patch("setup_wizard.CONFIG_PATH", config_file):
            save_config(config)
        saved = json.loads(config_file.read_text())
        assert saved["setup_completed"] is True


class TestValidateConfig:
    """Test config validation."""

    def test_valid_config(self):
        config = {
            "fund_name": "TestFund",
            "primary_email": "test@fund.com",
            "channels": {"email": {"enabled": True}},
        }
        issues = validate_config(config)
        assert issues == []

    def test_missing_fund_name(self):
        config = {
            "fund_name": "",
            "primary_email": "test@fund.com",
            "channels": {"email": {"enabled": True}},
        }
        issues = validate_config(config)
        assert any("fund_name" in i for i in issues)

    def test_missing_email(self):
        config = {
            "fund_name": "Test",
            "primary_email": "",
            "channels": {"email": {"enabled": True}},
        }
        issues = validate_config(config)
        assert any("primary_email" in i for i in issues)

    def test_no_channels_enabled(self):
        config = {
            "fund_name": "Test",
            "primary_email": "test@fund.com",
            "channels": {
                "email": {"enabled": False},
                "slack": {"enabled": False},
            },
        }
        issues = validate_config(config)
        assert any("channel" in i.lower() for i in issues)


class TestCheckConnectorStatus:
    """Test MCP connector detection."""

    def test_finds_configured_connectors(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "google-calendar": {"type": "http", "url": "https://gcal.mcp.claude.com/mcp"},
                "slack": {"type": "http", "url": "https://mcp.slack.com/mcp"},
            }
        }))
        with patch("setup_wizard.MCP_CONFIG_PATH", mcp_file):
            status = check_connector_status()
        assert status["calendar"]["has_connector"] is True
        assert status["slack"]["has_connector"] is True

    def test_missing_mcp_file(self, tmp_path):
        with patch("setup_wizard.MCP_CONFIG_PATH", tmp_path / "nonexistent.json"):
            status = check_connector_status()
        assert status["calendar"]["has_connector"] is False
        assert status["email"]["has_connector"] is False

    def test_partial_connectors(self, tmp_path):
        mcp_file = tmp_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "ms365": {"type": "http", "url": "https://microsoft365.mcp.claude.com/mcp"},
            }
        }))
        with patch("setup_wizard.MCP_CONFIG_PATH", mcp_file):
            status = check_connector_status()
        # ms365 covers both email (outlook) and calendar (outlook)
        assert status["email"]["has_connector"] is True
        assert status["calendar"]["has_connector"] is True
        assert status["slack"]["has_connector"] is False


class TestGetSetupSummary:
    """Test summary generation."""

    def test_includes_fund_name(self):
        config = {
            "fund_name": "Acme Ventures",
            "primary_user": "Jane",
            "primary_email": "jane@acme.vc",
            "channels": {"email": {"enabled": True, "provider": "outlook"}},
            "google_sheet_id": None,
        }
        summary = get_setup_summary(config)
        assert "Acme Ventures" in summary
        assert "Jane" in summary

    def test_shows_channel_status(self):
        config = {
            "fund_name": "Test",
            "primary_user": "User",
            "primary_email": "u@test.com",
            "channels": {
                "email": {"enabled": True, "provider": "gmail"},
                "whatsapp": {"enabled": False},
            },
            "google_sheet_id": None,
        }
        summary = get_setup_summary(config)
        assert "Enabled" in summary
        assert "Disabled" in summary

    def test_shows_whatsapp_targets(self):
        config = {
            "fund_name": "Test",
            "primary_user": "User",
            "primary_email": "u@test.com",
            "channels": {
                "whatsapp": {"enabled": True, "targets": ["VFT Group", "John"]},
            },
            "google_sheet_id": None,
        }
        summary = get_setup_summary(config)
        assert "VFT Group" in summary
