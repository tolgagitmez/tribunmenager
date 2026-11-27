import copy
import unittest
from original_roster_import import prepare_rows


class RosterImportTests(unittest.TestCase):
    def fixture(self):
        players=[dict(localIndex=i,name=f'Web Player {i}',webRole='CM',
            starterSlot=i+1 if i<11 else None,webValues={'passing':90}) for i in range(12)]
        snapshot=dict(schema=1,source='saved-web-roster',nativeApplied=False,players=players)
        mapping=dict(schema=1,teamId=1,nativeSlotOrder=list(reversed(range(11))),
            assignments=[dict(localIndex=i,nativePlayerId=i+100,firstName='Web',
                lastName=f'Player {i}',nativeRole='CM') for i in range(12)])
        return snapshot,mapping

    def test_reviewed_mapping_preserves_all_names_and_selected_starters(self):
        snapshot,mapping=self.fixture()
        before=copy.deepcopy(snapshot)
        rows,order=prepare_rows(snapshot,mapping)
        self.assertEqual(snapshot,before)
        self.assertEqual(len(rows),12)
        self.assertEqual(order,list(reversed(range(11))))
        self.assertEqual(rows[0]['nativePlayerId'],100)
        self.assertEqual(rows[0]['lastName'],'Player 0')
        self.assertNotIn('webValues',rows[0])

    def test_rejects_reserve_substitution_and_stale_names(self):
        for change in ('reserve','stale','duplicate','missing'):
            with self.subTest(change=change):
                snapshot,mapping=self.fixture()
                if change=='reserve':
                    mapping['nativeSlotOrder'][0]=11
                elif change=='stale':
                    mapping['assignments'][0]['lastName']='Wrong Player'
                elif change=='duplicate':
                    mapping['assignments'][1]['localIndex']=0
                else:
                    mapping['assignments'].pop()
                with self.assertRaises(ValueError):
                    prepare_rows(snapshot,mapping)
