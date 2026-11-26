import importlib.util
from pathlib import Path
import tempfile
import unittest
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
spec=importlib.util.spec_from_file_location('ownership',HERE/'native_audio_ownership.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class OwnershipTest(unittest.TestCase):
    def test_parse_and_reject_foreign(self):
        rows=m.parse_inputs('Sink Input #7\n\tSink: 2\n\tProperties:\n\t\tapplication.process.id = "123"\n')
        self.assertTrue(m.owned_input(rows,2,{123}))
        self.assertFalse(m.owned_input(rows,3,{123}))
        self.assertFalse(m.owned_input(rows,2,{124}))
        self.assertFalse(m.owned_input(rows+[{'sink':2,'pid':None}],2,{123}))
        self.assertFalse(m.owned_input([],2,{123}))
    def test_descendants(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'10/task/10';p.mkdir(parents=True)
            (p/'children').write_text('11 12')
            self.assertEqual(m.descendants(10,Path(t)),{10,11,12})
