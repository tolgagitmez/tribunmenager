"""Shared league standings projection for existing and rehearsed native scores."""
def project(teams,fix):
    standings=[]
    for t in teams:
        item={'slot':t['slot'],'club':t['name'],'manager':t['manager'],'played':0,'w':0,'d':0,'l':0,'gf':0,'ga':0,'points':0}
        for f in fix:
            if f['home_score'] is None or t['slot'] not in (f['home'],f['away']):continue
            home=t['slot']==f['home'];gf=f['home_score'] if home else f['away_score'];ga=f['away_score'] if home else f['home_score'];item['played']+=1;item['gf']+=gf;item['ga']+=ga;item['w']+=gf>ga;item['d']+=gf==ga;item['l']+=gf<ga;item['points']+=3 if gf>ga else 1 if gf==ga else 0
        standings.append(item)
    standings.sort(key=lambda a:(-a['points'],-(a['gf']-a['ga']),-a['gf'],a['slot']))
    return standings
