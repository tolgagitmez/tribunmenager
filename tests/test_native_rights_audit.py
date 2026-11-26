import sys
from pathlib import Path
import json
import unittest
import copy
import tempfile
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
sys.path.insert(0,str(HERE))
import native_rights_audit as a
class RightsTest(unittest.TestCase):
    def setUp(self):
        self.i=json.loads((HERE/'upstream-asset-inventory.json').read_text())
        self.u=json.loads((HERE/'upstream.json').read_text())
    def test_inventory_does_not_grant_rights(self):
        r=a.audit(self.i,self.u)
        self.assertGreater(r['pendingTrackedAssets'],500)
        self.assertFalse(r['commercialStreamingApproved'])
        self.assertFalse(r['assetRedistributionApproved'])
        self.assertFalse(r['productionEnabled'])
    def test_revision_duplicate_and_false_approval(self):
        for modify in (lambda i:i.update(upstreamRevision='other'),lambda i:i['assets'].append(i['assets'][0]),lambda i:i['assets'][0].update(status='approved'),lambda i:i['assets'][0].update(path='data/../secret')):
            i=copy.deepcopy(self.i);modify(i)
            with self.assertRaises(ValueError):a.audit(i,self.u)
    def test_runtime_inventory_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for n in ('data','media','databases','locale'):(root/n).mkdir()
            (root/'media'/'asset.png').write_bytes(b'asset')
            self.assertEqual(len(a.runtime_inventory(root)),1)
            (root/'data'/'alias').symlink_to(root/'media'/'asset.png')
            with self.assertRaises(ValueError):a.runtime_inventory(root)
