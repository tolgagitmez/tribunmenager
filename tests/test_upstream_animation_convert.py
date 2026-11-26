import base64,importlib.util,math,struct,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
spec=importlib.util.spec_from_file_location("convert",HERE/"upstream-animation-convert.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def fixture():
    return "\n".join(["player,0,0,0,0,20,0,-1,0"]+[f"{n},0,0,0,0,1,20,0,0,0,-1" for n in m.NAMES[1:]]+["extension,football,10,0,-.5,.1","<type>movement</type>"])
class ConvertTest(unittest.TestCase):
    def test_axis_and_time(self):
        c=m.parse(fixture());self.assertEqual(m.basis((0,-1,0)),(1,0,0))
        self.assertEqual(m.basis((0,0,1)),(0,1,0))
        self.assertEqual(c["tracks"]["body"][1][1],(0,0,0,1))
        g=m.gltf([{"name":n} for n in m.NAMES],{"test":c})
        self.assertEqual(len(g["animations"][0]["channels"]),14)
        self.assertEqual(g["accessors"][0]["max"],[.2])
        self.assertEqual(g["animations"][0]["extras"]["footballContactKeys"][0]["position"],(.5,.1,0))
        b=base64.b64decode(g["buffers"][0]["uri"].split(",")[1])
        self.assertEqual(len(b),g["buffers"][0]["byteLength"])
        view=g["bufferViews"][1];self.assertEqual(struct.unpack_from("<6f",b,view["byteOffset"]),(0,0,0,1,0,0))
    def test_malformed(self):
        for bad in [fixture().replace("player,0","player,-1",1),fixture().replace("body,0,0,0,0,1","body,0,0,0,0,0",1),fixture().replace("left_ankle","wrong",1),fixture().replace("0,-1,0","0,nan,0",1)]:
            with self.assertRaises(ValueError):m.parse(bad)
    def test_skeleton_validation(self):
        xml="<object>"+"".join(f"<node><name>{n}</name><position>0,0,1</position></node>" for n in m.NAMES[1:])+"</object>"
        nodes=m.skeleton(xml)
        self.assertEqual(len(nodes),14);self.assertEqual(nodes[1]["translation"],(0,1,0))
        self.assertEqual(len(nodes[0]["children"]),13)
        with self.assertRaises(ValueError):m.skeleton("<object/>")
