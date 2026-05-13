'''
Copyright 2019 Broadcom. The term "Broadcom" refers to Broadcom Inc.
and/or its subsidiaries.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''

import sys
import os
import pytest
from unittest.mock import patch

from ztp.ZTPLib import runCommand, getCfg
from .testlib import createPySymlink
sys.path.append(getCfg('plugins-dir'))

createPySymlink(getCfg('plugins-dir')+'/connectivity-check')
from connectivity_check import ConnectivityCheck, logger


def _run_plugin_capture_logs(input_json, tmpdir):
    '''Helper: run the plugin with the given JSON, return (exit_code, info_messages).'''
    d = tmpdir.mkdir("valid")
    fh = d.join("input.json")
    fh.write(input_json)
    info_messages = []
    plugin = ConnectivityCheck(str(fh))
    with patch.object(logger, 'info',
                      side_effect=lambda fmt, *args: info_messages.append(fmt % args if args else fmt)):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            plugin.main()
    return pytest_wrapped_e.value.code, info_messages

class TestClass(object):

    '''!
    This class allow to define unit tests for class ConnectivityCheck
    '''

    def test_data_hardening_test1(self, tmpdir):
        '''!
        Test case when we call the plugin with incomplete or wrong data
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
            "Foo": "empty"
        }
        """)
        connectivity_check = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            connectivity_check.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    def test_data_hardening_test2(self, tmpdir):
        '''!
        Test case when we call the plugin with incomplete or wrong data
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
            "ztp": { }
        }
        """)
        connectivity_check = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            connectivity_check.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    def test_ping_localhost(self, tmpdir):
        '''!
        Test case pinging IPV4 localhost:
        Verify that pinging IPV4 localhost succeeds
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
                "connectivity-check": {
                    "ping-hosts": "127.0.0.1",
                    "deadline": 15
                  }
        }
        """)
        connectivity_check = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            connectivity_check.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 0

    def test_ping_non_routable_address(self, tmpdir):
        '''!
        Test case pinging non routable IPV4 address:
        Verify that pinging IPV4 non routable address fails
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
                "01-connectivity-check": {
                    "retry-count": 2,
                    "retry-interval": 15,
                    "timeout": "10",
                    "ping-hosts": ["192.0.2.1", 123]
                  }
        }
        """)
        connectivity_check = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            connectivity_check.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    def test_ping_ipv6_localhost(self, tmpdir):
        '''!
        Test case pinging IPV6 localhost
        Verify that pinging IPV6 localhost succeeds
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
                "connectivity-check": {
                    "ping6-hosts": ["0:0:0:0:0:0:0:1"],
                    "retry-count": -2,
                    "retry-interval": -15
                  }
        }
        """)
        connectivity_check = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            connectivity_check.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 0

    def test_ping_ipv6_non_routable_address(self, tmpdir):
        '''!
        Test case pinging non routable IPV6 address:
        Verify that pinging IPV6 non routable address fails
        '''
        d = tmpdir.mkdir("valid")
        fh = d.join("input.json")
        fh.write("""
        {
                "connectivity-check": {
                    "ping6-hosts": ["0:0:0:0:0:0:0:1", "fe:80:0:0:0:0:0:1"],
                    "retry-count": 2
                  }
        }
        """)
        plugin = ConnectivityCheck(str(fh))
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            plugin.main()
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    @pytest.mark.parametrize("host,family", [
        ("127.0.0.1",       "IPv4"),
        ("0:0:0:0:0:0:0:1", "IPv6"),
    ])
    def test_ping_hosts_logged_with_correct_family(self, tmpdir, host, family):
        '''!
        A host listed under "ping-hosts" must be labeled with its actual
        address family in both per-host and summary logs, and must not appear
        under the other family's summary.
        '''
        other = "IPv6" if family == "IPv4" else "IPv4"
        exit_code, messages = _run_plugin_capture_logs("""
        {
                "connectivity-check": {
                    "ping-hosts": ["%s"],
                    "deadline": 15
                  }
        }
        """ % host, tmpdir)
        assert exit_code == 0
        joined = "\n".join(messages)
        assert "%s host" % family in joined, \
            "expected per-host log to label %s address: %r" % (family, messages)
        assert any("All %s hosts" % family in m for m in messages), \
            "expected summary log to say 'All %s hosts': %r" % (family, messages)
        assert not any("All %s hosts" % other in m for m in messages), \
            "%s address must not be labelled %s: %r" % (family, other, messages)

    def test_reachable_host_does_not_log_not_reachable(self, tmpdir):
        '''!
        A host that pings successfully must NOT
        produce a "not reachable" log line.
        '''
        exit_code, messages = _run_plugin_capture_logs("""
        {
                "connectivity-check": {
                    "ping-hosts": "127.0.0.1",
                    "deadline": 15
                  }
        }
        """, tmpdir)
        assert exit_code == 0
        assert not any("not reachable" in m for m in messages), \
            "reachable host should not produce 'not reachable' log: %r" % messages
        assert any("is reachable" in m for m in messages), \
            "expected a 'is reachable' log for the successful ping: %r" % messages

    def test_unreachable_host_does_not_log_reachable(self, tmpdir):
        '''!
        A host that fails to ping must NOT produce an "is reachable" log line.
        '''
        exit_code, messages = _run_plugin_capture_logs("""
        {
                "connectivity-check": {
                    "ping-hosts": ["192.0.2.1"],
                    "retry-count": 1,
                    "retry-interval": 1,
                    "timeout": 1
                  }
        }
        """, tmpdir)
        assert exit_code == 1
        assert not any("is reachable" in m for m in messages), \
            "unreachable host should not produce 'is reachable' log: %r" % messages
        assert any("not reachable" in m for m in messages), \
            "expected a 'not reachable' log for the failed ping: %r" % messages

    def test_mixed_v4_and_v6_in_ping_hosts(self, tmpdir):
        '''!
        Mixed input under the v4-keyed field: each host should be labelled
        according to its actual address family in both per-host and summary logs.
        '''
        exit_code, messages = _run_plugin_capture_logs("""
        {
                "connectivity-check": {
                    "ping-hosts": ["127.0.0.1", "0:0:0:0:0:0:0:1"],
                    "deadline": 15
                  }
        }
        """, tmpdir)
        assert exit_code == 0
        assert any("All IPv4 hosts" in m and "127.0.0.1" in m for m in messages), \
            "v4 bucket summary missing: %r" % messages
        assert any("All IPv6 hosts" in m and "0:0:0:0:0:0:0:1" in m for m in messages), \
            "v6 bucket summary missing: %r" % messages
