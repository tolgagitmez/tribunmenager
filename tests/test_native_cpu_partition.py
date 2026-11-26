import importlib.util
from pathlib import Path
import tempfile
import unittest
p=Path(__file__).resolve().parents[1]/'integrations/league-soccer/native_cpu_partition.py'
spec=importlib.util.spec_from_file_location('partition',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CpuPartitionTest(unittest.TestCase):
    def test_partition(self):
        self.assertEqual(m.partition([1,3,5,7,9,11],2),[[1,5,9],[3,7,11]])
        with self.assertRaises(ValueError):m.partition([1,2,3],2)
        self.assertEqual(m.affinity_command(['node','a'],[1,3]),['taskset','-c','1,3','node','a'])
    def test_cgroup(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for n,v in {'cpu.stat':'usage_usec 100\nnr_periods 20\nnr_throttled 3\nthrottled_usec 25\n','cpu.max':'200000 100000','memory.current':'1024','memory.max':'max'}.items():(p/n).write_text(v)
            r=m.counters(p)
            self.assertEqual(r['quotaCpus'],2)
            self.assertEqual(r['memoryCurrentBytes'],1024)
            self.assertEqual(m.delta(r,dict(r,nr_throttled=5))['nr_throttled'],2)
            self.assertIsNone(r['memoryLimitBytes'])
