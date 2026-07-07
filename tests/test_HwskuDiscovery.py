# Copyright 2026 Nexthop Systems Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import pytest
import sys
from unittest.mock import Mock, MagicMock, patch

# HwskuDiscovery imports swsscommon, utilities_common, and ztp.Logger at module
# level — these may be unavailable (C extensions) or would pollute the Logger
# tests if left mocked.  We save whatever is currently in sys.modules, install
# the mocks just long enough to satisfy the import, then restore the originals.
# The HwskuDiscovery module object retains its own references to the mocked
# symbols, so the tests below are unaffected; later-collected modules
# (test_Logger.py, test_configdb-json.py, …) see the real modules.
_MOCK_KEYS = [
    'swsscommon', 'swsscommon.swsscommon',
    'utilities_common', 'utilities_common.hwsku',
    'ztp.Logger',
]
_saved_modules = {k: sys.modules.get(k) for k in _MOCK_KEYS}

_mock_swss = MagicMock()
sys.modules['swsscommon'] = _mock_swss
sys.modules['swsscommon.swsscommon'] = _mock_swss

_mock_hwsku_module = MagicMock()
_mock_hwsku_module.get_available_hwskus = MagicMock(return_value=[])
sys.modules['utilities_common'] = MagicMock()
sys.modules['utilities_common.hwsku'] = _mock_hwsku_module
sys.modules['ztp.Logger'] = MagicMock()

from ztp.HwskuDiscovery import HwskuDiscoveryManager, create_hwsku_discovery_manager  # noqa: E402

for _k, _v in _saved_modules.items():
    if _v is None:
        del sys.modules[_k]
    else:
        sys.modules[_k] = _v


class TestHwskuDiscoveryManager:
    """Unit tests for HwskuDiscoveryManager class."""

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_init_default(self, mock_time, mock_getCfg):
        """Test initialization with required parameters."""
        mock_time.monotonic.return_value = 1000.0
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        hwsku_list = ['NH-4010', 'NH-4020']
        current_index = 0

        manager = HwskuDiscoveryManager(hwsku_list, current_index)

        assert manager._hwsku_list == hwsku_list
        assert manager._current_index == current_index
        assert manager._hwsku_timer == 1000.0
        assert manager.get_port_timeout() == 180   # default
        assert manager.get_discovery_timeout() == 600  # default

    @patch('ztp.HwskuDiscovery.getCfg')
    def test_init_with_custom_timeouts(self, mock_getCfg):
        """Test initialization with custom timeout values."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-port-up-timeout':
                return 120
            elif key == 'hwsku-discovery-timeout':
                return 900
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect

        manager = HwskuDiscoveryManager(['NH-4010', 'NH-4020'], 1)

        assert manager.get_port_timeout() == 120
        assert manager.get_discovery_timeout() == 900
        assert manager._current_index == 1

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_port_timeout_exceeds_discovery_timeout(self, mock_getCfg, mock_get_hwskus):
        """Test factory returns None when port timeout is >= discovery timeout."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-port-up-timeout':
                return 600
            elif key == 'hwsku-discovery-timeout':
                return 600
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect
        mock_get_hwskus.return_value = ['NH-4010', 'NH-4010-128x400G']

        manager = create_hwsku_discovery_manager(Mock())

        assert manager is None

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_no_hwsku_list(self, mock_getCfg, mock_get_hwskus):
        """Test factory function when no HWSKU list is available."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        mock_get_hwskus.return_value = []

        manager = create_hwsku_discovery_manager(Mock())

        assert manager is None

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_single_hwsku(self, mock_getCfg, mock_get_hwskus):
        """Test factory function disables discovery when only one HWSKU is available."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        mock_get_hwskus.return_value = ['NH-4010']

        manager = create_hwsku_discovery_manager(Mock())

        assert manager is None

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_success_no_current_hwsku(self, mock_getCfg, mock_get_hwskus):
        """Test successful factory creation with no current HWSKU."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        mock_get_hwskus.return_value = ['NH-4010', 'NH-4010-128x400G']

        mock_config_db = Mock()
        mock_config_db.get_entry.return_value = {}

        manager = create_hwsku_discovery_manager(mock_config_db)

        assert manager is not None
        assert manager._hwsku_list == ['NH-4010', 'NH-4010-128x400G']
        assert manager._current_index == 0

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_success_with_current_hwsku(self, mock_getCfg, mock_get_hwskus):
        """Test successful factory creation with current HWSKU."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        mock_get_hwskus.return_value = ['NH-4010', 'NH-4010-128x400G', 'NH-4010-256x200G']

        mock_config_db = Mock()
        mock_config_db.get_entry.return_value = {'hwsku': 'NH-4010-128x400G'}

        manager = create_hwsku_discovery_manager(mock_config_db)

        assert manager is not None
        assert manager._current_index == 1  # Index of 'NH-4010-128x400G'

    @patch('ztp.HwskuDiscovery.get_available_hwskus')
    @patch('ztp.HwskuDiscovery.getCfg')
    def test_factory_get_entry_exception(self, mock_getCfg, mock_get_hwskus):
        """Test factory function handles get_entry exceptions gracefully."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value
        mock_get_hwskus.return_value = ['NH-4010', 'NH-4010-128x400G']

        mock_config_db = Mock()
        mock_config_db.get_entry.side_effect = Exception("Redis connection error")

        manager = create_hwsku_discovery_manager(mock_config_db)

        assert manager is not None
        assert manager._current_index == 0

    @patch('ztp.HwskuDiscovery.getCfg')
    def test_init_empty_list_raises(self, mock_getCfg):
        """Test that empty hwsku_list raises AssertionError in constructor."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        with pytest.raises(AssertionError, match="hwsku_list must be non-empty"):
            HwskuDiscoveryManager([], 0)

    @patch('ztp.HwskuDiscovery.getCfg')
    def test_get_current_hwsku(self, mock_getCfg):
        """Test getting current HWSKU."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        manager = HwskuDiscoveryManager(['NH-4010', 'NH-4010-128x400G'], 1)

        assert manager.get_current_hwsku() == 'NH-4010-128x400G'

    @patch('ztp.HwskuDiscovery.getCfg')
    def test_try_next_hwsku_success(self, mock_getCfg):
        """Test successfully moving to next HWSKU."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        manager = HwskuDiscoveryManager(['NH-4010', 'NH-4010-128x400G', 'NH-4010-256x200G'], 0)
        result = manager.try_next_hwsku()

        assert result is True
        assert manager._current_index == 1

    @patch('ztp.HwskuDiscovery.getCfg')
    def test_try_next_hwsku_wrap_around(self, mock_getCfg):
        """Test wrapping around to first HWSKU after trying all."""
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        manager = HwskuDiscoveryManager(['NH-4010', 'NH-4010-128x400G', 'NH-4010-256x200G'], 2)
        result = manager.try_next_hwsku()

        assert result is True
        assert manager._current_index == 0

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_reset_timer(self, mock_time, mock_getCfg):
        """Test resetting the timer."""
        mock_time.monotonic.return_value = 1000.0
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        manager = HwskuDiscoveryManager(['NH-4010'], 0)
        assert manager._hwsku_timer == 1000.0

        mock_time.monotonic.return_value = 2000.0
        manager.reset_timer()

        assert manager._hwsku_timer == 2000.0

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_check_port_timeout_just_started(self, mock_time, mock_getCfg):
        """Test checking port timeout immediately after timer starts."""
        mock_time.monotonic.return_value = 1000.0
        mock_getCfg.side_effect = lambda key, default_value=None: default_value

        manager = HwskuDiscoveryManager(['NH-4010'], 0)

        assert manager.check_port_timeout() is False

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_check_port_timeout_not_exceeded(self, mock_time, mock_getCfg):
        """Test checking port timeout when not exceeded."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-port-up-timeout':
                return 60
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect
        mock_time.monotonic.return_value = 1000.0
        manager = HwskuDiscoveryManager(['NH-4010'], 0)

        mock_time.monotonic.return_value = 1030.0
        assert manager.check_port_timeout() is False

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_check_port_timeout_exceeded(self, mock_time, mock_getCfg):
        """Test checking port timeout when exceeded."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-port-up-timeout':
                return 60
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect
        mock_time.monotonic.return_value = 1000.0
        manager = HwskuDiscoveryManager(['NH-4010'], 0)

        mock_time.monotonic.return_value = 1070.0
        assert manager.check_port_timeout() is True

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_check_discovery_timeout_not_exceeded(self, mock_time, mock_getCfg):
        """Test checking discovery timeout when not exceeded."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-discovery-timeout':
                return 600
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect
        mock_time.monotonic.return_value = 1000.0
        manager = HwskuDiscoveryManager(['NH-4010'], 0)

        mock_time.monotonic.return_value = 1300.0
        assert manager.check_discovery_timeout() is False

    @patch('ztp.HwskuDiscovery.getCfg')
    @patch('ztp.HwskuDiscovery.time')
    def test_check_discovery_timeout_exceeded(self, mock_time, mock_getCfg):
        """Test checking discovery timeout when exceeded."""
        def getCfg_side_effect(key, default_value=None):
            if key == 'hwsku-discovery-timeout':
                return 600
            return default_value

        mock_getCfg.side_effect = getCfg_side_effect
        mock_time.monotonic.return_value = 1000.0
        manager = HwskuDiscoveryManager(['NH-4010'], 0)

        mock_time.monotonic.return_value = 1700.0
        assert manager.check_discovery_timeout() is True
