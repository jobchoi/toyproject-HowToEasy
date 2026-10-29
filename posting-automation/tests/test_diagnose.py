"""Regression: diagnosis must never open the shared database or load a draft."""
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class DiagnoseTests(unittest.TestCase):
    def test_diagnose_does_not_open_database_or_draft(self):
        import naver_browser_probe as probe
        manager = MagicMock()
        browser = manager.__enter__.return_value.chromium.launch.return_value
        with patch.object(probe, 'sync_playwright', return_value=manager), \
             patch.object(probe, 'configure_korean_fonts'), \
             patch('naver_trial_support.Journal', side_effect=AssertionError('must not open DB')), \
             patch('naver_trial_support.read_draft', side_effect=AssertionError('must not read draft')), \
             patch('browser_diagnostics.system_check'), \
             patch('browser_diagnostics.browser_check', return_value=0), \
             patch.object(sys, 'argv', ['probe', '--diagnose']):
            self.assertEqual(probe.main(), 0)
        browser.close.assert_called_once()
