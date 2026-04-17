import sys
import os
import json
import pytest
import tempfile

from ztp.ZTPLib import runCommand, getCfg

class TestClass(object):

    '''
    This class defines unit tests for the ztp-config.j2 template
    '''

    def __render_template(self, ztp_inband, ztp_ipv4="true", ztp_ipv6="true",
                          hwsku="TestSKU", platform="test-platform"):
        '''
        Render the ztp-config.j2 template with given parameters
        Returns the parsed JSON configuration

        Args:
            ztp_inband: "true" or "false" for inband ZTP
            ztp_ipv4: "true" or "false" for IPv4 support
            ztp_ipv6: "true" or "false" for IPv6 support
            hwsku: Hardware SKU (default: "TestSKU" for testing)
            platform: Platform name (default: "test-platform" for testing)
        '''
        template_path = "/usr/lib/ztp/templates/ztp-config.j2"

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp_file:
            output_file = tmp_file.name

        try:
            # Build the JSON arguments for sonic-cfggen
            json_args = (
                '{{"ZTP_INBAND": "{}", "ZTP_IPV4": "{}", "ZTP_IPV6": "{}", '
                '"PRODUCT_NAME": "Test Product", "SERIAL_NO": "TEST123"}}'
            ).format(ztp_inband, ztp_ipv4, ztp_ipv6)

            # Render the template using sonic-cfggen
            cmd = 'sonic-cfggen -k {} -a \'{}\' -p -t {} > {}'.format(
                hwsku, json_args, template_path, output_file
            )
            (rc, cmd_stdout, cmd_stderr) = runCommand(cmd)

            if rc != 0:
                raise Exception("Failed to render template: {}".format(cmd_stderr))

            with open(output_file, 'r') as f:
                config = json.load(f)

            return config
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)

    @pytest.mark.parametrize("inband", ["true", "false"])
    def test_ztp_config_inband(self, inband):
        '''
        Test inband ZTP configuration:
        - When inband="true": COPP_TRAP table with inband_dhcp, ports admin_status="up"
        - When inband="false": No COPP_TRAP table, ports admin_status="down"
        '''
        config = self.__render_template(ztp_inband=inband)

        if inband == "true":
            # Verify COPP_TRAP table exists with inband_dhcp
            assert 'COPP_TRAP' in config, "COPP_TRAP table should exist when ZTP_INBAND is true"
            assert 'inband_dhcp' in config['COPP_TRAP'], "inband_dhcp should be in COPP_TRAP table"

            # Verify inband_dhcp configuration
            inband_dhcp = config['COPP_TRAP']['inband_dhcp']
            assert inband_dhcp['trap_ids'] == 'dhcp,dhcpv6,dhcp_l2,dhcpv6_l2', \
                "inband_dhcp trap_ids should be dhcp,dhcpv6,dhcp_l2,dhcpv6_l2"
            assert inband_dhcp['trap_group'] == 'queue4_group3', \
                "inband_dhcp trap_group should be queue4_group3"
            assert inband_dhcp['always_enabled'] == 'true', \
                "inband_dhcp always_enabled should be true"

            # Verify all ports have admin_status "up"
            for port_name, port_config in config['PORT'].items():
                assert port_config['admin_status'] == 'up', \
                    f"Port {port_name} admin_status should be 'up' when inband is true"
        else:
            # Verify COPP_TRAP table does not exist
            assert 'COPP_TRAP' not in config, \
                "COPP_TRAP table should not exist when ZTP_INBAND is false"

            # Verify all ports have admin_status "down"
            for port_name, port_config in config['PORT'].items():
                assert port_config['admin_status'] == 'down', \
                    f"Port {port_name} admin_status should be 'down' when inband is false"

    def test_ztp_config_section(self):
        '''
        Test that the ZTP config section correctly reflects all input variables
        '''
        # Test config 1: inband=true, ipv4=true, ipv6=false
        config1 = self.__render_template(ztp_inband="true", ztp_ipv4="true", ztp_ipv6="false")

        assert 'ZTP' in config1, "ZTP table should exist"
        assert 'mode' in config1['ZTP'], "mode should be in ZTP table"

        ztp_mode1 = config1['ZTP']['mode']
        assert ztp_mode1['profile'] == 'active', "profile should be 'active'"
        assert ztp_mode1['inband'] == 'true', "inband should be 'true'"
        assert ztp_mode1['out-of-band'] == 'true', "out-of-band should be 'true'"
        assert ztp_mode1['ipv4'] == 'true', "ipv4 should be 'true'"
        assert ztp_mode1['ipv6'] == 'false', "ipv6 should be 'false'"
        assert ztp_mode1['product-name'] == 'Test Product', "product-name should match"
        assert ztp_mode1['serial-no'] == 'TEST123', "serial-no should match"

        # Test config 2: inband=false, ipv4=false, ipv6=true (swapped values)
        config2 = self.__render_template(ztp_inband="false", ztp_ipv4="false", ztp_ipv6="true")

        ztp_mode2 = config2['ZTP']['mode']
        assert ztp_mode2['profile'] == 'active', "profile should be 'active'"
        assert ztp_mode2['inband'] == 'false', "inband should be 'false'"
        assert ztp_mode2['out-of-band'] == 'true', "out-of-band should be 'true'"
        assert ztp_mode2['ipv4'] == 'false', "ipv4 should be 'false'"
        assert ztp_mode2['ipv6'] == 'true', "ipv6 should be 'true'"
        assert ztp_mode2['product-name'] == 'Test Product', "product-name should match"
        assert ztp_mode2['serial-no'] == 'TEST123', "serial-no should match"

    def test_ztp_config_port_attributes(self):
        '''
        Test that PORT entries contain expected attributes and handle optional fields correctly
        '''
        config = self.__render_template(ztp_inband="true")

        # Verify PORT table exists and has entries
        assert 'PORT' in config, "PORT table should exist"
        assert len(config['PORT']) > 0, "PORT table should have at least one port"

        # Check that each port has required attributes
        for port_name, port_config in config['PORT'].items():
            # Required attributes
            assert 'index' in port_config, f"Port {port_name} should have index"
            assert 'lanes' in port_config, f"Port {port_name} should have lanes"
            assert 'mtu' in port_config, f"Port {port_name} should have mtu"
            assert port_config['mtu'] == '9100', f"Port {port_name} mtu should be 9100"
            assert 'admin_status' in port_config, f"Port {port_name} should have admin_status"

            # Optional attributes (may or may not be present depending on platform)
            # Just verify they're strings if present
            for optional_attr in ['alias', 'speed', 'valid_speeds', 'fec', 'role']:
                if optional_attr in port_config:
                    assert isinstance(port_config[optional_attr], str), \
                        f"Port {port_name} {optional_attr} should be a string"

    def test_ztp_config_device_metadata(self):
        '''
        Test that DEVICE_METADATA is always generated correctly
        '''
        config = self.__render_template(ztp_inband="true")

        # Verify DEVICE_METADATA exists
        assert 'DEVICE_METADATA' in config, "DEVICE_METADATA should exist"
        assert 'localhost' in config['DEVICE_METADATA'], "localhost should be in DEVICE_METADATA"

        localhost = config['DEVICE_METADATA']['localhost']
        assert localhost['type'] == 'not-provisioned', "type should be not-provisioned"
        assert localhost['hostname'] == 'sonic', "hostname should be sonic"
        assert 'hwsku' in localhost, "hwsku should be present"
        assert 'platform' in localhost, "platform should be present"
        assert 'mac' in localhost, "mac should be present"

