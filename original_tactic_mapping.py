"""Read-only comparison and explicitly reviewed native team tactic data.

No conversion is treated as equivalent to Tribun Manager's old engine.
The native controls themselves remain unchanged.
"""
import math
import xml.etree.ElementTree as ET
from original_catalog import KNOWN_TACTICS,xml_fragment

WEB_KEYS={'mentality','playstyle','marking','offside','line','passing','width',
          'onLoss','onWin','fullbacks','crossing','shooting','press','tempo','aggression'}

# Semantic correspondence only. No automatic values or claims of equivalence.
RELATED={
    'press':['team_pressure'],
    'width':['position_offense_width_factor','position_defense_width_factor'],
    'onWin':['counter_attack'],
    'playstyle':['counter_attack','support_distance'],
    'passing':['support_distance'],
    'mentality':['position_offense_midfieldfocus','position_offense_sidefocus_strength','dribble_offensiveness'],
}


def compare_web_tactics(web):
    if not isinstance(web,dict) or set(web)-WEB_KEYS:
        raise ValueError('Explicit supported web tactic fields required')
    return dict(rows=[dict(webKey=k,webValue=v,nativeCandidates=RELATED.get(k,[]),
                           status='review-required' if k in RELATED else 'no-direct-equivalent')
                      for k,v in web.items()],
                nativeApplied=False,behaviorEquivalenceVerified=False)


def plan_native_tactics(raw,reviewed):
    """Apply only native values explicitly selected by a reviewer to team data.
    The three upstream memory defaults can be materialized; never invent others.
    """
    if not isinstance(reviewed,dict) or not reviewed or set(reviewed)-set(KNOWN_TACTICS):
        raise ValueError('Explicit known native tactic controls required')
    tree=xml_fragment(raw)
    nodes={}
    for node in tree:
        if node.tag in nodes:
            raise ValueError('Duplicate native tactic field')
        nodes[node.tag]=node
    changes=[]
    for key,value in reviewed.items():
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('Native tactic must be in 0..1')
        node=nodes.get(key)
        if node is None:
            if key not in {'counter_attack','support_distance','team_pressure'}:
                raise ValueError('Native tactic not present in existing database')
            old=.5
            node=ET.SubElement(tree,key)
        else:
            if len(node) or node.attrib:
                raise ValueError('Invalid existing native tactic field')
            old=float(node.text or '')
            if not math.isfinite(old) or not 0<=old<=1:
                raise ValueError('Invalid existing native tactic value')
        node.text=format(value,'.9g')
        changes.append(dict(key=key,previous=old,reviewed=float(node.text)))
    return dict(tacticsXml=''.join(ET.tostring(n,encoding='unicode') for n in tree),
                changes=changes,behaviorEquivalenceVerified=False,nativeApplied=False)
