import math
import unittest
from original_skill_mapping import factor,plan_profile


class SkillMappingTests(unittest.TestCase):
    def test_peak_and_age_boundaries_match_pinned_formula(self):
        self.assertAlmostEqual(factor(.5,27),1.2)
        self.assertAlmostEqual(factor(.5,14+1),.6*(1+math.sin(math.pi/26)))
        self.assertAlmostEqual(factor(.5,40),.6)
        self.assertAlmostEqual(factor(.5,20),factor(.5,34))
        for base in (0,1.1,float('nan')):
            with self.assertRaises(ValueError):
                factor(base,27)

    def test_inverse_and_unmapped_field(self):
        report=plan_profile(.5,27,'<technical_shot>0.4</technical_shot><physical_shotpower>0.7</physical_shotpower>',{'shooting':90,'strength':95})
        self.assertEqual(report['proposed'][0]['profile'],.75)
        self.assertAlmostEqual(report['proposed'][0]['predictedNativeStat'],.9)
        self.assertIn('<physical_shotpower>0.7</physical_shotpower>',report['profileXml'])
        self.assertEqual(report['unsupported'],['strength'])
        self.assertFalse(report['crossEngineEquivalenceVerified'])

    def test_unreachable_and_missing_are_not_silently_clamped(self):
        report=plan_profile(.2,40,'<technical_shot>0.4</technical_shot>',{'shooting':99,'passing':60})
        self.assertEqual(len(report['unresolved']),2)
        self.assertEqual(report['proposed'],[])
        for value in (-1,101,float('inf'),True):
            with self.assertRaises(ValueError):
                plan_profile(.5,27,'<technical_shot>0.4</technical_shot>',{'shooting':value})
