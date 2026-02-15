"""Tests for CLI review_generate step."""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from cli.steps.review_generate import step_review_generate


def _sample_config():
    return {
        "marketplace": {"name": "TestMarket", "industry": "Testing"},
        "participant_types": [
            {"name": "Seller", "slug": "seller", "role": "supply"},
            {"name": "Buyer", "slug": "buyer", "role": "demand"},
        ],
        "communication": {
            "conversation_rules": [
                {"initiator": "buyer", "receiver": "seller"},
            ]
        },
    }


class TestStepReviewGenerate:
    @patch("cli.steps.review_generate.questionary")
    def test_confirm_returns_true(self, mock_questionary):
        mock_confirm = MagicMock()
        mock_confirm.ask.return_value = True
        mock_questionary.confirm.return_value = mock_confirm

        result = step_review_generate(_sample_config())
        assert result is True

    @patch("cli.steps.review_generate.questionary")
    def test_deny_returns_false(self, mock_questionary):
        mock_confirm = MagicMock()
        mock_confirm.ask.return_value = False
        mock_questionary.confirm.return_value = mock_confirm

        result = step_review_generate(_sample_config())
        assert result is False

    @patch("cli.steps.review_generate.questionary")
    def test_ctrl_c_returns_false(self, mock_questionary):
        mock_confirm = MagicMock()
        mock_confirm.ask.side_effect = KeyboardInterrupt
        mock_questionary.confirm.return_value = mock_confirm

        result = step_review_generate(_sample_config())
        assert result is False

    @patch("cli.steps.review_generate.questionary")
    def test_none_result_returns_false(self, mock_questionary):
        mock_confirm = MagicMock()
        mock_confirm.ask.return_value = None
        mock_questionary.confirm.return_value = mock_confirm

        result = step_review_generate(_sample_config())
        assert result is False
