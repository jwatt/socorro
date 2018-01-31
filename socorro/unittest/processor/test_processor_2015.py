import ujson

from configman import ConfigurationManager
from configman.dotdict import DotDict
from mock import Mock, patch

from socorro.processor.processor_2015 import Processor2015
from socorro.processor.general_transform_rules import (
    CPUInfoRule,
    OSInfoRule
)
from socorro.unittest.testbase import TestCase


class TestProcessor2015(TestCase):

    def test_Processor2015_init(self):
        cm = ConfigurationManager(
            definition_source=Processor2015.get_required_config(),
            values_source_list=[],
        )
        config = cm.get_config()
        config.logger = Mock()

        Processor2015(config)

    def test_process_crash_existing_processed_crash(self):
        cm = ConfigurationManager(
            definition_source=Processor2015.get_required_config(),
            values_source_list=[],
        )
        config = cm.get_config()
        config.logger = Mock()

        config.processor_name = 'dwight'

        p = Processor2015(config, rules=[
            CPUInfoRule,
            OSInfoRule,
        ])
        raw_crash = DotDict({
            'uuid': '1'
        })
        raw_dumps = {}
        processed_crash = DotDict({
            'processor_notes': 'we\'ve been here before; yep',
            'started_datetime': '2014-01-01T00:00:00'
        })

        with patch('socorro.processor.processor_2015.utc_now') as faked_utcnow:
            faked_utcnow.return_value = '2015-01-01T00:00:00'
            processed_crash = p.process_crash(
                raw_crash,
                raw_dumps,
                processed_crash
            )

        assert processed_crash.success
        assert processed_crash.started_datetime == '2015-01-01T00:00:00'
        assert processed_crash.startedDateTime == '2015-01-01T00:00:00'
        assert processed_crash.completed_datetime == '2015-01-01T00:00:00'
        assert processed_crash.completeddatetime == '2015-01-01T00:00:00'
        expected = (
            "dwight; Processor2015; earlier processing: 2014-01-01T00:00:00;"
            " we've been here before; yep"
        )
        assert processed_crash.processor_notes == expected

    @patch('socorro.processor.breakpad_transform_rules.subprocess')
    def test_process_over_255_chars(self, mocked_subprocess_module):
        thread_over_255_chars = {
            "frames": [
                {
                    "file": "nsTerminator.cpp:604367e1fa5e",
                    "frame": 0,
                    "function": ("mozilla::`anonymous namespace::"
                                 "RunWatchdog(void *)" + "a" * 255),
                    "function_offset": "0x0",
                    "line": 151,
                    "module": "xul.dll",
                    "module_offset": "0x783f2b",
                    "offset": "0x67903f2b",
                    "registers": {
                        "eax": "0x0000003f",
                        "ebp": "0x163ff96c",
                        "ebx": "0x0cf44450",
                        "ecx": "0x691e3698",
                        "edi": "0x76d3f551",
                        "edx": "0x01dc1010",
                        "efl": "0x00000246",
                        "eip": "0x67903f2b",
                        "esi": "0x0000003f",
                        "esp": "0x163ff968"
                    },
                    "trust": "context"
                }
            ]
        }
        stackwalker_output_str = ujson.dumps({
            "crash_info": {
                "address": "0x0",
                "crashing_thread": 0,
                "type": "EXC_BAD_ACCESS / KERN_INVALID_ADDRESS"
            },
            "status": "OK",
            "crashing_thread": thread_over_255_chars,
            "threads": [thread_over_255_chars],
            "system_info": {
                "os": "Windows NT",
                "cpu_arch": "x86"
            },
            "sensitive": {
                "exploitability": "high"
            },
        })

        cm = ConfigurationManager(
            definition_source=(
                Processor2015.get_required_config(),
            ),
            values_source_list=[]
        )
        config = cm.get_config()
        config.logger = Mock()
        config.processor_name = 'dwight'

        mocked_subprocess_handle = (
            mocked_subprocess_module.Popen.return_value
        )
        mocked_subprocess_handle.wait.return_value = 0
        mocked_subprocess_handle.stdout.read.return_value = (
            stackwalker_output_str
        )
        p = Processor2015(config)

        raw_crash = DotDict({
            "uuid": "00000000-0000-0000-0000-000002140504",
            "CrashTime": "1336519554",
            "SecondsSinceLastCrash": "86985",
            "PluginHang": "1",
            "ProductName": "Firefox",
            "Version": "19",
            "BuildID": "20121031"
        })
        raw_dumps = {"upload_file_minidump": "a_fake_dump.dump"}

        processed_crash = p.process_crash(
            raw_crash,
            raw_dumps,
            DotDict()
        )

        assert processed_crash.success
        expected = (
            'dwight; Processor2015; SigTrunc: signature truncated due to length'
        )
        assert processed_crash.processor_notes == expected
        assert processed_crash.signature.startswith('shutdownhang')
        assert len(processed_crash.signature) == 255
