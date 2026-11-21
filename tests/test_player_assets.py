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

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'assets/player'
# This package shares its directory with the independent procedural character.
# Its builder owns only these licensed MakeHuman derivative artifacts.
LICENSED_ARTIFACTS = {
    Path(name) for name in [
        'CREDITS.md', 'LICENSE-CC0.txt', 'SOURCE-LICENSE.md', 'footballer.glb',
        'manifest.json', 'player-model-data.js', 'skeleton.json',
        'source/makehuman-base.obj.gz', 'source/makehuman-default.mhskel.gz',
        'source/makehuman-default_weights.mhw.gz', 'source/provenance.json',
        'textures/fabric-detail.png', 'textures/skin-detail.png',
    ]
}
spec = importlib.util.spec_from_file_location('tribun_asset_builder', ROOT / 'tools/build-player-assets.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
check_spec = importlib.util.spec_from_file_location(
    'tribun_asset_rebuild_verifier', ROOT / 'tools/verify-player-asset-rebuild.py')
rebuild_verifier = importlib.util.module_from_spec(check_spec)
check_spec.loader.exec_module(rebuild_verifier)


def unpack(target):
    for name in ['makehuman-base.obj', 'makehuman-default.mhskel', 'makehuman-default_weights.mhw']:
        (target / name).write_bytes(gzip.decompress((PACKAGE / 'source' / (name + '.gz')).read_bytes()))
    for src, name in [('SOURCE-LICENSE.md', 'makehuman-LICENSE.md'), ('LICENSE-CC0.txt', 'makehuman-LICENSE.ASSETS.md'), ('source/provenance.json', 'makehuman-provenance.json')]:
        (target / name).write_bytes((PACKAGE / src).read_bytes())


def source_mesh():
    with tempfile.TemporaryDirectory(prefix='tribun-weight-source-') as directory:
        source = Path(directory)
        unpack(source)
        points, uv, groups = builder.obj(source / 'makehuman-base.obj')
        skeleton = json.loads((source / 'makehuman-default.mhskel').read_text())
        weights = json.loads((source / 'makehuman-default_weights.mhw').read_text())
        return points, uv, groups, skeleton, weights


class PlayerAssetBuildTests(unittest.TestCase):
    def test_joint_weight_smoothing_uses_six_jacobi_rounds_and_only_source_body_edges(self):
        # A four-edge body loop with a hard half/half weight boundary has a
        # known diffusion result. Helper faces must contribute no adjacency.
        points = np.array([[-.01,-.01,0], [.01,-.01,0], [.01,.01,0], [-.01,.01,0],
                           [.02,0,0], [.03,0,0], [.04,0,0],
                           [-.01,-.29,0], [.01,-.29,0], [.01,-.31,0], [-.01,-.31,0]], dtype=float)
        weights = np.zeros((len(points),19));weights[:2,6] = 1;weights[2:4,7] = 1
        weights[4:7,18] = 1;weights[7:,8] = 1
        original = weights.copy();original_points = points.copy()
        groups = {'body': [[(i, i) for i in range(4)], [(i, i) for i in range(7,11)]],
                  'joint-l-elbow': [[(0,0),(4,0),(5,0),(6,0)]]}
        frames = {}
        for side,x in [('L',0),('R',1)]:
            for bone,y in [('upper_arm',1),('forearm',0),('shin',-2),('hand',-.29)]:
                frames[bone+'.'+side] = (np.array([x,y,0.]),np.array([x,y-.1,0.]))
        derived, _ = builder.smooth_joint_weights(points, weights, groups, frames)
        np.testing.assert_array_equal(weights, original)
        np.testing.assert_array_equal(points, original_points)
        np.testing.assert_allclose(derived[:2,6], .5078125, atol=1e-14, rtol=0)
        np.testing.assert_allclose(derived[2:4,6], .4921875, atol=1e-14, rtol=0)
        np.testing.assert_allclose(derived[:4,6]+derived[:4,7], 1, atol=1e-14, rtol=0)
        np.testing.assert_array_equal(derived[4:], original[4:])

    def test_derived_joint_weights_preserve_source_bind_geometry_and_wrist_skin(self):
        source, uv, groups, skeleton, weights = source_mesh()
        smoother = builder.smooth_joint_weights
        captured = {}

        def record(points, source_weights, body_groups, frames):
            before_points = points.copy();before_weights = source_weights.copy()
            derived, stats = smoother(points, source_weights, body_groups, frames)
            np.testing.assert_array_equal(points, before_points)
            np.testing.assert_array_equal(source_weights, before_weights)
            captured.update(points=before_points, original=before_weights, derived=derived.copy(), frames=frames)
            return derived, stats

        with patch.object(builder, 'smooth_joint_weights', side_effect=record):
            smoothed, smoothed_indices, smoothed_bones, _ = builder.skin_geometry(source, uv, groups, skeleton, weights)

        def unchanged(points, source_weights, body_groups, frames):
            _, stats = smoother(points, source_weights, body_groups, frames)
            return source_weights.copy(), stats

        with patch.object(builder, 'smooth_joint_weights', side_effect=unchanged):
            original, original_indices, original_bones, _ = builder.skin_geometry(source, uv, groups, skeleton, weights)
        np.testing.assert_array_equal(smoothed[:,:8], original[:,:8], 'runtime weight repair must not change positions, normals or UVs')
        np.testing.assert_array_equal(smoothed[:,16:], original[:,16:], 'runtime weight repair must not change material or color geometry')
        np.testing.assert_array_equal(smoothed_indices, original_indices)
        self.assertEqual(smoothed_bones, original_bones)
        self.assertFalse(np.array_equal(smoothed[:,8:16], original[:,8:16]), 'the derivative must actually repair runtime influences')

        points = captured['points'];original_weights = captured['original'];derived = captured['derived']
        body_ids = np.array(sorted({i for face in groups['body'] for i,_ in face}))
        body_mask = np.zeros(len(points), dtype=bool);body_mask[body_ids] = True
        selected = np.zeros(len(points), dtype=bool)
        for side in ('L','R'):
            for bone,radius in [('upper_arm',.18),('forearm',.12),('shin',.15)]:
                within = np.linalg.norm(points-captured['frames'][bone+'.'+side][0],axis=1)<radius
                selected |= within
                self.assertGreater(np.count_nonzero(within & body_mask & np.any(np.abs(derived-original_weights)>1e-12,axis=1)),20)
        changed = np.any(np.abs(derived-original_weights)>1e-12,axis=1)
        self.assertGreater(np.count_nonzero(changed),300)
        self.assertFalse(np.any(changed & ~(selected & body_mask)), 'only the six selected body joint patches may change')
        self.assertTrue(np.isfinite(derived).all());self.assertGreaterEqual(float(derived.min()),0)
        np.testing.assert_allclose(derived[body_ids].sum(axis=1),1,atol=2e-15,rtol=0)
        protected = original_weights[:,[8,15]].sum(axis=1)>.001
        for side in ('L','R'):
            protected |= np.linalg.norm(points-captured['frames']['hand.'+side][0],axis=1)<.10
        protected &= body_mask
        self.assertGreater(np.count_nonzero(protected),500)
        np.testing.assert_array_equal(derived[protected],original_weights[protected], 'hand, finger and wrist weights stay source-derived without smoothing')

    def test_packaged_sources_rebuild_every_artifact_with_verified_binary_geometry_outside_repo(self):
        with tempfile.TemporaryDirectory(prefix='tribun-assets-rebuild-') as directory:
            out = Path(directory) / 'output'
            result = subprocess.run([sys.executable, str(ROOT / 'tools/build-player-assets.py'), '--from-package', '--output', str(out)], cwd=directory, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = {p.relative_to(out) for p in out.rglob('*') if p.is_file()}
            self.assertEqual(generated, LICENSED_ARTIFACTS)
            # Official sources, license, provenance, texture PNGs and every
            # manifest hash remain BYTE-EXACT. Only derived float attributes
            # may differ by less than 2e-6 from the packaged reviewed model.
            # NumPy/BLAS can otherwise produce differing last mantissa bits.
            report = rebuild_verifier.compare_packages(PACKAGE, out)
            self.assertGreater(report['float32ComponentsChecked'], 150000)
            self.assertGreater(report['glbViewsChecked'], 6)
            self.assertLessEqual(report['maxFloat32Delta'], 2e-6)
            self.assertLessEqual(report['maxFloat64Delta'], 1e-10)

    def test_rebuild_verification_does_not_accept_material_geometry_or_license_changes(self):
        # Tolerance is only for sub-micrometre float32 rounding, not an
        # altered shape, weight painting, index, source, texture or manifest.
        a = np.array([.10, 1.2, -.4],dtype='<f4').tobytes()
        b = np.array([.10, 1.201, -.4],dtype='<f4').tobytes()
        with self.assertRaisesRegex(AssertionError, 'geometry differs'):
            rebuild_verifier.compare_float32(a, b, 'tampered vertex', {
                'maxFloat32Delta':0.,'float32ComponentsChecked':0})
        with self.assertRaises(AssertionError):
            rebuild_verifier.compare_structure(
                {'model':{'weights':[1.,0.,0.]}},
                {'model':{'weights':[0.,1.,0.]}}, 'modified weights')
        with tempfile.TemporaryDirectory(prefix='tribun-source-integrity-') as directory:
            pkg = Path(directory)
            for relative in LICENSED_ARTIFACTS:
                target=pkg/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((PACKAGE/relative).read_bytes())
            source = pkg/'source/provenance.json'
            source.write_bytes(source.read_bytes()+b'\\n')
            with self.assertRaisesRegex(AssertionError,'SHA256 integrity failure'):
                rebuild_verifier.verify_manifest(pkg)

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
