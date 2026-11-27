import unittest
from original_tactic_mapping import compare_web_tactics,plan_native_tactics
from original_catalog import tactics


class TacticMappingTests(unittest.TestCase):
    def test_web_controls_are_not_silently_converted(self):
        report=compare_web_tactics({'press':86,'width':'wide','offside':'on','tempo':80})
        self.assertEqual(report['rows'][0]['nativeCandidates'],['team_pressure'])
        self.assertEqual(len(report['rows'][1]['nativeCandidates']),2)
        self.assertEqual(report['rows'][2]['status'],'no-direct-equivalent')
        self.assertEqual(report['rows'][3]['nativeCandidates'],[])
        self.assertFalse(report['nativeApplied'])

    def test_explicit_native_controls_preserve_unselected_fields(self):
        raw='<position_offense_width_factor>0.45</position_offense_width_factor><position_defense_width_factor>0.55</position_defense_width_factor>'
        result=plan_native_tactics(raw,{'team_pressure':.8,'position_offense_width_factor':.7})
        values={t['key']:t['value'] for t in tactics(result['tacticsXml'])}
        self.assertEqual(values['team_pressure'],.8)
        self.assertEqual(values['position_offense_width_factor'],.7)
        self.assertEqual(values['position_defense_width_factor'],.55)
        self.assertEqual(result['changes'][0]['previous'],.5)
        self.assertFalse(result['behaviorEquivalenceVerified'])

    def test_rejects_missing_unknown_duplicate_and_invalid_fields(self):
        for reviewed in ({'tempo':.8},{'team_pressure':True},{'team_pressure':1.1},{'team_pressure':float('nan')},{'dribble_offensiveness':.7}):
            with self.subTest(reviewed=reviewed),self.assertRaises(ValueError):
                plan_native_tactics('',reviewed)
        with self.assertRaises(ValueError):
            plan_native_tactics('<team_pressure>0.3</team_pressure><team_pressure>0.4</team_pressure>',{'team_pressure':.8})
