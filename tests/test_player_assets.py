"""Offline reproduction and rejection of altered third-party source evidence."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'assets/player'
spec = importlib.util.spec_from_file_location('tribun_asset_builder', ROOT / 'tools/build-player-assets.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def unpack(target):
    for name in ['makehuman-base.obj', 'makehuman-default.mhskel', 'makehuman-default_weights.mhw']:
        (target / name).write_bytes(gzip.decompress((PACKAGE / 'source' / (name + '.gz')).read_bytes()))
    for src, name in [('SOURCE-LICENSE.md', 'makehuman-LICENSE.md'), ('LICENSE-CC0.txt', 'makehuman-LICENSE.ASSETS.md'), ('source/provenance.json', 'makehuman-provenance.json')]:
        (target / name).write_bytes((PACKAGE / src).read_bytes())


class PlayerAssetBuildTests(unittest.TestCase):
    def test_packaged_sources_rebuild_every_artifact_byte_for_byte_outside_repo(self):
        with tempfile.TemporaryDirectory(prefix='tribun-assets-rebuild-') as directory:
            out = Path(directory) / 'output'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/build-player-assets.py'), '--from-package', '--output', str(out)], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            existing = {p.relative_to(PACKAGE) for p in PACKAGE.rglob('*') if p.is_file()}
            generated = {p.relative_to(out) for p in out.rglob('*') if p.is_file()}
            self.assertEqual(generated, existing)
            for name in sorted(existing):
                with self.subTest(file=str(name)):
                    self.assertEqual((out / name).read_bytes(), (PACKAGE / name).read_bytes())

    def assert_rejected(self, name):
        with tempfile.TemporaryDirectory(prefix='tribun-assets-rejection-') as directory:
            source = Path(directory) / 'source'
            source.mkdir()
            unpack(source)
            file = source / name
            file.write_bytes(file.read_bytes() + b'\nchanged\n')
            out = Path(directory) / 'output'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/build-player-assets.py'), '--source-dir', str(source), '--output', str(out)], cwd=directory, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(name + ': source hash differs', result.stderr)
            self.assertFalse(out.exists(), 'Unverified input must be rejected before any output is generated')

    def test_changed_weight_data_is_rejected_before_generation(self):
        self.assert_rejected('makehuman-default_weights.mhw')

    def test_changed_license_text_is_rejected_before_generation(self):
        self.assert_rejected('makehuman-LICENSE.ASSETS.md')

    def test_matching_source_bytes_do_not_accept_rewritten_provenance(self):
        with tempfile.TemporaryDirectory(prefix='tribun-assets-provenance-') as directory:
            source = Path(directory)
            unpack(source)
            original = json.loads((source / 'makehuman-provenance.json').read_text())
            for key, value in [('commit', 'unreviewed'), ('repository', 'https://example.test/mirror'), ('assetLicense', 'AGPL-3.0')]:
                with self.subTest(field=key), self.assertRaises(ValueError):
                    altered = copy.deepcopy(original)
                    altered[key] = value
                    builder.verify_source(source, altered)
            for field, value in [('sourceURL', 'https://example.test/unverified.obj'), ('sha256', '0' * 64), ('bytes', 1)]:
                with self.subTest(recordField=field), self.assertRaises(ValueError):
                    altered = copy.deepcopy(original)
                    altered['files'][0][field] = value
                    builder.verify_source(source, altered)

    def test_changed_rig_requires_an_explicit_reference_review(self):
        with tempfile.TemporaryDirectory(prefix='tribun-assets-rig-') as directory:
            root = Path(directory)
            (root / 'humanoid-rig.js').write_text('unreviewed replacement')
            with patch.object(builder, 'ROOT', root), self.assertRaisesRegex(ValueError, 'reviewed rig reference'):
                builder.reference_frames()


if __name__ == '__main__':
    unittest.main()
