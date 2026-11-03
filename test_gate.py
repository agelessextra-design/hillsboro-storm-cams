import datetime as dt, gate
U=dt.timezone.utc
def t(*a): return dt.datetime(*a,tzinfo=U)
S={'windows':[{'id':'a','start':'2026-11-05T22:00:00Z','hours':48,'label':'storm'}]}
c=[
 ('before window',  S, t(2026,11,5,21,59), False,'idle'),
 ('at start',       S, t(2026,11,5,22,0),  True,'active'),
 ('middle',         S, t(2026,11,6,22,0),  True,'active'),
 ('one min before end',S,t(2026,11,7,21,59),True,'active'),
 ('at end',         S, t(2026,11,7,22,0),  False,'idle'),
 ('empty schedule', {'windows':[]}, t(2026,11,5,22,0), False,'idle'),
 ('watch hourly on the hour', {'windows':[],'watch_hourly':True}, t(2026,11,5,9,2), True,'watch'),
 ('watch hourly between',     {'windows':[],'watch_hourly':True}, t(2026,11,5,9,25), False,'watch-wait'),
 ('window beats watch', {'windows':S['windows'],'watch_hourly':True}, t(2026,11,6,9,25), True,'active'),
 ('overlapping windows use the later end', {'windows':[{'start':'2026-11-05T22:00:00Z','hours':10},{'start':'2026-11-05T23:00:00Z','hours':48}]}, t(2026,11,6,12,0), True,'active'),
 ('bad entry ignored', {'windows':[{'start':'nonsense','hours':1}]}, t(2026,11,6,12,0), False,'idle'),
 ('start with offset time zone', {'windows':[{'start':'2026-11-05T14:00:00-08:00','hours':1}]}, t(2026,11,5,22,30), True,'active'),
]
bad=0
for name,s,now,run,state in c:
    r=gate.evaluate(s,now); ok=(r['run']==run and r['state']==state); bad+=0 if ok else 1
    print('PASS' if ok else 'FAIL',name,'->',r['run'],r['state'])
r=gate.evaluate(S,t(2026,11,5,10,0));print('next window reported:',r['next']['start'].isoformat())
print('failures:',bad)
