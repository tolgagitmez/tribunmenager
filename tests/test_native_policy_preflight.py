import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_policy_preflight import replay, blob_id

PATCH = '''RULE = "next"
def apply(root):
    edit(root, "ignored.cpp", [("a", "b")])
    edit(root, "src/onthepitch/aitactics.hpp", [("start", RULE + " end")])
    edit(root, "src/onthepitch/aitactics.hpp", [("end", "finish")])
'''

class HeaderPreflightTest(unittest.TestCase):
    def test_sequence_and_constants(self):
        self.assertEqual(replay('start', PATCH), ('next finish', 2))
    def test_missing_and_duplicate_anchor(self):
        for header in ('unknown', 'start start'):
            with self.assertRaises(ValueError):
                replay(header, PATCH)
    def test_conditional_edit_rejected(self):
        patch = PATCH + '    if root:\n        edit(root, "src/onthepitch/aitactics.hpp", [("finish", "done")])\n'
        with self.assertRaises(ValueError):
            replay('start', patch)
    def test_unsupported_dynamic_string(self):
        with self.assertRaises(ValueError):
            replay('start', PATCH.replace('RULE + " end"', 'str(root)'))
    def test_blob(self):
        self.assertEqual(blob_id(b'hello\n'), 'ce013625030ba8dba906f756967f9e9ca394464a')
