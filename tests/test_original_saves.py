import tempfile
from pathlib import Path
import unittest
from original_saves import locked_store, restore, commit, current_snapshot


class OriginalSavesTests(unittest.TestCase):
    def test_roundtrip_and_failed_exit_keeps_previous(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            first=base/'first'
            first.mkdir()
            (first/'saves/league').mkdir(parents=True)
            (first/'saves/league/autosave.sqlite').write_bytes(b'native bytes')
            (first/'football.config').write_text('not saved')
            with locked_store(base/'store') as root:
                self.assertTrue(commit(root,first,0))
                old=current_snapshot(root)
                second=base/'second'
                second.mkdir()
                restore(root,second)
                self.assertEqual((second/'saves/league/autosave.sqlite').read_bytes(),b'native bytes')
                self.assertFalse((second/'football.config').exists())
                (second/'saves/league/autosave.sqlite').write_bytes(b'new bytes')
                self.assertFalse(commit(root,second,1))
                self.assertEqual(current_snapshot(root),old)
                self.assertTrue(commit(root,second,0))
                self.assertNotEqual(current_snapshot(root),old)
                self.assertEqual((old/'league/autosave.sqlite').read_bytes(),b'native bytes')

    def test_journal_and_symlink_preserve_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            session=base/'session'
            saves=session/'saves'
            saves.mkdir(parents=True)
            (saves/'native.sqlite').write_bytes(b'original')
            with locked_store(base/'store') as root:
                commit(root,session,0)
                old=current_snapshot(root)
                (saves/'native.sqlite-wal').write_bytes(b'unsettled')
                with self.assertRaises(RuntimeError):
                    commit(root,session,0)
                self.assertEqual(current_snapshot(root),old)
                (saves/'native.sqlite-wal').unlink()
                (saves/'outside').symlink_to(base)
                with self.assertRaises(RuntimeError):
                    commit(root,session,0)
                self.assertEqual(current_snapshot(root),old)

    def test_second_session_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with locked_store(Path(d)) as root:
                with self.assertRaises(RuntimeError):
                    with locked_store(root):
                        self.fail('Duplicate session acquired lock')

    def test_missing_saves_preserves_previous(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            session=base/'session'
            session.mkdir()
            with locked_store(base/'store') as root:
                self.assertFalse(commit(root,session,0))
                self.assertIsNone(current_snapshot(root))


if __name__=='__main__':
    unittest.main()
