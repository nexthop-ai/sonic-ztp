# Copyright 2026 Nexthop Systems Inc. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import time
from typing import Optional, List
from swsscommon.swsscommon import ConfigDBConnector
from ztp.Logger import logger
from ztp.ZTPLib import getCfg
from utilities_common.hwsku import get_available_hwskus


DEFAULT_HWSKU_PORT_UP_TIMEOUT = 180
DEFAULT_HWSKU_DISCOVERY_TIMEOUT = 600


def create_hwsku_discovery_manager(config_db: ConfigDBConnector) -> Optional[HwskuDiscoveryManager]:
    '''!
    Factory function to create a HWSKU discovery manager.

    @param config_db ConfigDBConnector instance

    @return HwskuDiscoveryManager instance if enabled and valid, None otherwise
    '''
    port_timeout = getCfg('hwsku-port-up-timeout', default_value=DEFAULT_HWSKU_PORT_UP_TIMEOUT)
    discovery_timeout = getCfg('hwsku-discovery-timeout', default_value=DEFAULT_HWSKU_DISCOVERY_TIMEOUT)
    if port_timeout >= discovery_timeout:
        logger.warning(f'Disabling HWSKU discovery: hwsku-port-up-timeout ({port_timeout}) should not be longer '
                       f'than hwsku-discovery-timeout ({discovery_timeout})')
        return None

    hwsku_list = sorted(get_available_hwskus())

    if not hwsku_list:
        logger.warning('Disabling HWSKU discovery: HWSKU discovery enabled but no HWSKU list found')
        return None

    if len(hwsku_list) < 2:
        logger.info('Disabling HWSKU discovery: only one HWSKU available (%s), nothing to cycle' % hwsku_list[0])
        return None

    current_hwsku = None
    try:
        device_metadata = config_db.get_entry('DEVICE_METADATA', 'localhost')
        if device_metadata and 'hwsku' in device_metadata:
            current_hwsku = device_metadata['hwsku']
    except Exception as e:
        logger.warning(f'Failed to read current HWSKU from CONFIG_DB: {e}')

    if current_hwsku and current_hwsku in hwsku_list:
        current_index = hwsku_list.index(current_hwsku)
        logger.info('Starting HWSKU discovery from currently loaded HWSKU: %s (index %d)' %
                    (current_hwsku, current_index))
    else:
        current_index = 0
        if current_hwsku:
            logger.warning('Current HWSKU "%s" not in available list, starting from index 0' % current_hwsku)
        else:
            logger.info('No current HWSKU found, starting from index 0')

    logger.info('HWSKU discovery enabled. Will try: %s' % ', '.join(hwsku_list))

    return HwskuDiscoveryManager(hwsku_list, current_index)


class HwskuDiscoveryManager:
    '''!
    Manages HWSKU discovery state and operations.

    This class provides HWSKU discovery functionality for Zero Touch Provisioning.
    It manages cycling through available HWSKUs to find the correct hardware configuration.

    IMPORTANT: Do not instantiate this class directly. Use create_hwsku_discovery_manager()
    factory function instead, which ensures proper initialization and validation.
    '''

    def __init__(
        self,
        hwsku_list: List[str],
        current_index: int
    ) -> None:
        '''!
        Initialize HWSKU discovery manager.

        IMPORTANT: Do not call this constructor directly in production code.
        Use create_hwsku_discovery_manager() factory function instead, which ensures
        proper initialization and validation.

        @param hwsku_list List of available HWSKUs (must be non-empty)
        @param current_index Index of the current HWSKU to start from
        '''
        assert hwsku_list, "hwsku_list must be non-empty (use factory function)"
        assert current_index < len(hwsku_list), \
            f"current_index {current_index} out of range for hwsku_list length {len(hwsku_list)} (use factory function)"

        self._hwsku_list: List[str] = hwsku_list
        self._current_index: int = current_index
        self._port_timeout: int = getCfg('hwsku-port-up-timeout', default_value=DEFAULT_HWSKU_PORT_UP_TIMEOUT)
        self._discovery_timeout: int = getCfg('hwsku-discovery-timeout', default_value=DEFAULT_HWSKU_DISCOVERY_TIMEOUT)
        self._hwsku_timer: float = 0.0  # Will be set by reset_timer()
        self.reset_timer()

    def get_current_hwsku(self) -> str:
        return self._hwsku_list[self._current_index]

    def reset_timer(self) -> None:
        self._hwsku_timer = time.monotonic()

    def get_port_timeout(self) -> int:
        return self._port_timeout

    def get_discovery_timeout(self) -> int:
        return self._discovery_timeout

    def check_port_timeout(self) -> bool:
        elapsed = time.monotonic() - self._hwsku_timer
        return elapsed > self._port_timeout

    def check_discovery_timeout(self) -> bool:
        elapsed = time.monotonic() - self._hwsku_timer
        return elapsed > self._discovery_timeout

    def try_next_hwsku(self) -> bool:
        '''!
        Move to the next HWSKU in the list.

        @return True if moved to next HWSKU, False if not enabled
        '''
        current_hwsku = self.get_current_hwsku()

        # Move to next HWSKU (wrap around if necessary)
        self._current_index = (self._current_index + 1) % len(self._hwsku_list)

        next_hwsku = self.get_current_hwsku()
        logger.info('Moving from HWSKU %s to %s' % (current_hwsku, next_hwsku))

        return True
