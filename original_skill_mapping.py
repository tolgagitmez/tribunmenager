"""Experimental data-only conversion for a separate roster package.

Pinned upstream CalculateStat (src/utils.cpp) and curve (bluntmath.hpp).
A 0..100 web attribute is a proposed native 0.01..1 pre-condition target,
not proof of equal football performance. Native age and base_stat stay fixed.
"""
import math
import xml.etree.ElementTree as ET
from original_catalog import xml_fragment

# Only clearly related attributes. Passing and tackling are narrower native
# skills, not substitutes for high passes or sliding tackles.
SKILL_MAP={
    'balance':'physical_balance','reactions':'physical_reaction',
    'acceleration':'physical_acceleration','pace':'physical_velocity',
    'endurance':'physical_stamina','agility':'physical_agility',
    'tackling':'technical_standingtackle','dribbling':'technical_dribble',
    'passing':'technical_shortpass','heading':'technical_header',
    'shooting':'technical_shot','composure':'mental_calmness',
    'vision':'mental_vision',
}


def factor(base,age):
    if (type(base) not in (int,float) or not math.isfinite(base) or not 0<base<=1 or
        type(age) is not int or not 15<=age<=50):
        raise ValueError('Invalid native age or base stat')
    t=1-min(abs(age-27)/13,1)*.5
    age_factor=math.sin((t-.5)*math.pi)
    return 2*base*(age_factor*.5+.5)*1.2


def plan_profile(base,age,raw_xml,web_values):
    if not isinstance(web_values,dict):
        raise ValueError('Explicit web skill values required')
    scale=factor(base,age)
    tree=xml_fragment(raw_xml)
    nodes={}
    for node in tree:
        if node.tag in nodes or len(node) or node.attrib:
            raise ValueError('Ambiguous native player profile')
        nodes[node.tag]=node
    proposed=[]
    unresolved=[]
    for web,native in SKILL_MAP.items():
        if web not in web_values:
            continue
        value=web_values[web]
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:
            raise ValueError('Invalid web skill: '+web)
        target=max(.01,value/100)
        profile=target/scale
        if native not in nodes or profile>1:
            unresolved.append(dict(web=web,native=native,reason='missing-native-field' if native not in nodes else 'outside-bounded-profile-range',target=target))
            continue
        old=float(nodes[native].text or '')
        if not math.isfinite(old) or not 0<=old<=1:
            raise ValueError('Invalid existing native profile value')
        nodes[native].text=format(profile,'.9g')
        encoded=float(nodes[native].text)
        proposed.append(dict(web=web,native=native,target=target,profile=encoded,
            predictedNativeStat=max(.01,min(1,encoded*scale))))
    return dict(profileXml=''.join(ET.tostring(n,encoding='unicode') for n in tree),
                proposed=proposed,unresolved=unresolved,
                unsupported=sorted(set(web_values)-set(SKILL_MAP)),
                crossEngineEquivalenceVerified=False,conditionMultiplierIncluded=False)
