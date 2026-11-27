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


    def test_unique_exact_name_suggestions_never_replace_unmatched_players(self):
        from original_roster_import import suggest_mapping
        snapshot,_=self.fixture()
        team=dict(id=1,players=[dict(id=i+100,name=f'web player {i}') for i in range(12)],
                  formation=[dict(slot=i+1,role='CM') for i in range(11)],truncated=False)
        result=suggest_mapping(snapshot,team)
        self.assertTrue(result['complete'])
        self.assertTrue(result['requiresReview'])
        self.assertFalse(result['nativeApplied'])
        self.assertEqual(result['mapping']['nativeSlotOrder'],list(range(11)))
        self.assertEqual(result['mapping']['assignments'][0]['nativePlayerId'],100)
        team['players'][0]['name']='Other player'
        incomplete=suggest_mapping(snapshot,team)
        self.assertFalse(incomplete['complete'])
        self.assertEqual(incomplete['unresolved'][0]['reason'],'ambiguous-or-missing-name')
        self.assertIn(None,incomplete['mapping']['nativeSlotOrder'])
        self.assertNotIn(100,[r['nativePlayerId'] for r in incomplete['mapping']['assignments']])

    def test_duplicate_names_and_incompatible_formation_block_suggestions(self):
        from original_roster_import import suggest_mapping
        snapshot,_=self.fixture()
        team=dict(id=1,players=[dict(id=i+100,name=f'Web Player {i}') for i in range(12)],
                  formation=[dict(slot=i+1,role='CM') for i in range(11)],truncated=False)
        team['formation'][0]['role']='GK'
        self.assertFalse(suggest_mapping(snapshot,team)['complete'])
        team['formation'][0]['role']='CM'
        team['players'][1]['name']=team['players'][0]['name']
        self.assertFalse(suggest_mapping(snapshot,team)['complete'])
