import copy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import original_roster_import as importer
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

    def test_reviewed_skill_values_come_only_from_the_saved_player(self):
        snapshot,mapping=self.fixture()
        assignment=mapping['assignments'][0]
        assignment.update(reviewedSkills=['passing'],webValues={'passing':1})
        rows,_=prepare_rows(snapshot,mapping)
        self.assertEqual(rows[0]['webValues'],{'passing':90})
        self.assertNotIn('webValues',rows[1])
        for invalid in (['heading'],['goalkeeping'],['passing','passing'],'passing',[{}]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                prepare_rows(snapshot,{**mapping,
                    'assignments':[{**assignment,'reviewedSkills':invalid},*mapping['assignments'][1:]]})

    def test_cli_applies_only_reviewed_changes_to_a_disposable_team_pack(self):
        snapshot,mapping=self.fixture()
        snapshot['players'].append(dict(localIndex=12,name='Web Player 12',webRole='CM',starterSlot=None))
        mapping['assignments'].append(dict(localIndex=12,nativePlayerId=112,firstName='Web',
            lastName='Player 12',nativeRole='CM'))
        mapping['assignments'][0]['reviewedSkills']=['passing']
        mapping['reviewedTactics']={'team_pressure':.8}
        formation=''.join(f'<p{i}><position>0,0</position><role>CM</role></p{i}>' for i in range(1,12))
        tactics='<position_offense_width_factor>0.35</position_offense_width_factor>'
        profile='<technical_shortpass>0.4</technical_shortpass><technical_highpass>0.3</technical_highpass>'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            build=root/'build'
            original=build/'databases/default/database.sqlite'
            original.parent.mkdir(parents=True)
            with sqlite3.connect(original) as db:
                db.execute('CREATE TABLE teams(id INTEGER PRIMARY KEY,formation_xml TEXT,tactics_xml TEXT)')
                db.executemany('INSERT INTO teams VALUES(?,?,?)',[(1,formation,tactics),(2,formation,tactics)])
                db.execute('CREATE TABLE players(id INTEGER PRIMARY KEY,team_id INTEGER,nationalteam_id INTEGER,firstname TEXT,lastname TEXT,role TEXT,base_stat REAL,age INTEGER,profile_xml TEXT,formationorder INTEGER)')
                db.executemany('INSERT INTO players VALUES(?,?,?,?,?,?,?,?,?,?)',
                    [(i,1 if i<113 else 2,0,'Native',str(i),'CM',.5,27,profile,
                        {111:112,112:111}.get(i,i)) for i in range(100,114)])
            original_bytes=original.read_bytes()
            snapshot_path=root/'export.json'
            mapping_path=root/'review.json'
            snapshot_path.write_text(json.dumps(snapshot),encoding='utf-8')
            mapping_path.write_text(json.dumps(mapping),encoding='utf-8')

            def inspect_runtime(args,*,cwd,env):
                self.assertEqual(args,[str(cwd/'gameplayfootball')])
                self.assertEqual((cwd/'databases/default/database.sqlite').read_bytes(),original_bytes)
                with sqlite3.connect(cwd/'databases/tribun-roster-pilot/database.sqlite') as db:
                    self.assertEqual(db.execute('SELECT id FROM players WHERE team_id=1 ORDER BY formationorder')
                        .fetchall(),[(i,) for i in [*range(110,99,-1),112,111]])
                    actual=db.execute('SELECT age,base_stat,profile_xml FROM players WHERE id=100').fetchone()
                    self.assertEqual(actual,(27,.5,profile.replace('0.4','0.75')))
                    self.assertEqual(db.execute('SELECT DISTINCT profile_xml FROM players WHERE id!=100').fetchall(),[(profile,)])
                    self.assertEqual(db.execute('SELECT formation_xml,tactics_xml FROM teams WHERE id=1').fetchone(),
                        (formation,tactics+'<team_pressure>0.8</team_pressure>'))
                    self.assertEqual(db.execute('SELECT formation_xml,tactics_xml FROM teams WHERE id=2').fetchone(),
                        (formation,tactics))
                return SimpleNamespace(returncode=0)

            output=StringIO()
            with (patch.object(sys,'argv',['original_roster_import.py',str(snapshot_path),str(mapping_path)]),
                  patch.object(importer.engine,'cache_root',return_value=root),
                  patch.object(importer.engine,'verify_install',return_value=build),
                  patch.object(importer.engine,'check_config'),
                  patch.object(importer,'populate',side_effect=shutil.copytree),
                  patch.object(importer.subprocess,'run',side_effect=inspect_runtime) as run,
                  redirect_stdout(output)):
                importer.main()
            run.assert_called_once()
            report,_=json.JSONDecoder().raw_decode(output.getvalue())
            self.assertEqual(report['experimentalSkillProfilesWritten'],1)
            self.assertEqual([item['key'] for item in report['experimentalTacticsWritten']],['team_pressure'])
            self.assertFalse(report['nativeMenuLoadVerified'])
            self.assertEqual(original.read_bytes(),original_bytes)

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
