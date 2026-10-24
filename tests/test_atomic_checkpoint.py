import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from travel_agent.session_context import write_json


class AtomicCheckpointTests(TestCase):
    def test_transient_replace_denial_retries_file_only_and_preserves_data(self):
        with TemporaryDirectory() as folder:
            target=Path(folder)/'context.json';write_json(target,{'old':True})
            original=Path.replace;calls=[]
            def replace(p,t):
                calls.append(1)
                if len(calls)==1:
                    self.assertEqual(json.loads(target.read_text()),{'old':True})
                    raise PermissionError('fixture transient lock')
                return original(p,t)
            with patch.object(Path,'replace',replace),patch('travel_agent.session_context.time.sleep'):
                write_json(target,{'new':True})
            self.assertEqual(json.loads(target.read_text()),{'new':True})
            self.assertEqual(len(calls),2)

    def test_persistent_denial_keeps_target_and_reports_failure(self):
        with TemporaryDirectory() as folder:
            target=Path(folder)/'context.json';write_json(target,{'old':True})
            with patch.object(Path,'replace',side_effect=PermissionError),patch('travel_agent.session_context.time.sleep'),self.assertRaises(PermissionError):
                write_json(target,{'new':True})
            self.assertEqual(json.loads(target.read_text()),{'old':True})
