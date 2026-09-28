# Memory view

What each policy did to memory. Pruned and superseded fact text is
recovered from graph snapshots (cells run with "save_graph": true).


## NOMEM__mock
policy `NOMEM` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 12 · pruned: 0 · write rejections: 0 · superseded still visible: 3
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/NOMEM__mock.graph.html` · data: `graphs/NOMEM__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/NOMEM__mock.replay.html` · 5 sessions · 2 with a supersession

## P0__mock
policy `P0` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 12 · pruned: 0 · write rejections: 0 · superseded still visible: 3
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/P0__mock.graph.html` · data: `graphs/P0__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/P0__mock.replay.html` · 5 sessions · 2 with a supersession

## P1__mock
policy `P1:ttl_days=35` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 6 · pruned: 6 · write rejections: 0 · superseded still visible: 1
- **pruned fact text** (6):
    - ~~Carol: I love hiking on weekends.~~ (written by conversation)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by conversation)
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by conversation)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by conversation)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by conversation)
    - ~~Carol: I adopted a kitten named Whiskers, my first pet.~~ (written by conversation)
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/P1__mock.graph.html` · data: `graphs/P1__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/P1__mock.replay.html` · 5 sessions · 2 with a supersession

## P2__mock
policy `P2` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 9 · pruned: 3 · write rejections: 0 · superseded still visible: 0
- **pruned fact text** (3):
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by conversation)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by conversation)
    - ~~Carol: Work at Initech has been stressful lately.~~ (written by conversation)
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/P2__mock.graph.html` · data: `graphs/P2__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/P2__mock.replay.html` · 5 sessions · 2 with a supersession

## P3__mock
policy `P3` · model `mock` · topology `-`
- total facts ever written: 11
- active at end: 11 · pruned: 0 · write rejections: 1 · superseded still visible: 3
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/P3__mock.graph.html` · data: `graphs/P3__mock.graph.json` · communities: 2 · god nodes: carol, dan, i love hiking on weekends.
- **replay** (scrub through time): `graphs/P3__mock.replay.html` · 5 sessions · 2 with a supersession

## P4__mock
policy `P4` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 11 · pruned: 1 · write rejections: 0 · superseded still visible: 3
- **pruned fact text** (1):
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by conversation)
- **superseded facts** (3):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=1709164800.0
- interactive graph: `graphs/P4__mock.graph.html` · data: `graphs/P4__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/P4__mock.replay.html` · 5 sessions · 2 with a supersession

## P5__mock
policy `P5` · model `mock` · topology `-`
- total facts ever written: 12
- active at end: 5 · pruned: 7 · write rejections: 0 · superseded still visible: 0
- **pruned fact text** (7):
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by conversation)
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by conversation)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by conversation)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by conversation)
    - ~~Carol: Work at Initech has been stressful lately.~~ (written by conversation)
    - ~~Dan: My band released our first album called Midnight Drive.~~ (written by conversation)
    - ~~Carol: My mentor at work is very supportive.~~ (written by conversation)
- **superseded facts** (2):
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=1707868800.0
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=1707868800.0
- interactive graph: `graphs/P5__mock.graph.html` · data: `graphs/P5__mock.graph.json` · communities: 2 · god nodes: carol, dan, i play guitar in a local band, my favorite instrument.
- **replay** (scrub through time): `graphs/P5__mock.replay.html` · 5 sessions · 1 with a supersession
