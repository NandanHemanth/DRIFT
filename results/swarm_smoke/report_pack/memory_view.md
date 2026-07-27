# Memory view

What each policy did to memory. Pruned and superseded fact text is
recovered from graph snapshots (cells run with "save_graph": true).


## independent__NOMEM
policy `NOMEM` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P0
policy `P0` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P1
policy `P1:ttl_days=14` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P2
policy `P2` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P3
policy `P3` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P4
policy `P4` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## independent__P5
policy `P5` · model `-` · topology `independent`
- total facts ever written: -
- active at end: - · pruned: - · write rejections: - · superseded still visible: -
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__NOMEM
policy `NOMEM` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 28 · pruned: 0 · write rejections: 0 · superseded still visible: 5
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P0
policy `P0` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 28 · pruned: 0 · write rejections: 0 · superseded still visible: 5
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P1
policy `P1:ttl_days=14` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 6 · pruned: 22 · write rejections: 0 · superseded still visible: 0
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P2
policy `P2` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 23 · pruned: 5 · write rejections: 0 · superseded still visible: 0
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P3
policy `P3` · model `-` · topology `orchestrator`
- total facts ever written: 25
- active at end: 25 · pruned: 0 · write rejections: 3 · superseded still visible: 5
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P4
policy `P4` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 25 · pruned: 3 · write rejections: 0 · superseded still visible: 5
- (no snapshot; enable "save_graph": true for fact-level views)

## orchestrator__P5
policy `P5` · model `-` · topology `orchestrator`
- total facts ever written: 28
- active at end: 11 · pruned: 17 · write rejections: 0 · superseded still visible: 1
- (no snapshot; enable "save_graph": true for fact-level views)

## shared__NOMEM
policy `NOMEM` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 28 · pruned: 0 · write rejections: 0 · superseded still visible: 5
- **superseded facts** (5):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__NOMEM.graph.html` · data: `graphs/shared__NOMEM.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P0
policy `P0` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 28 · pruned: 0 · write rejections: 0 · superseded still visible: 5
- **superseded facts** (5):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__P0.graph.html` · data: `graphs/shared__P0.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P1
policy `P1:ttl_days=14` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 6 · pruned: 22 · write rejections: 0 · superseded still visible: 0
- **pruned fact text** (22):
    - ~~Alice: My favorite hobby is painting landscapes.~~ (written by agent_0)
    - ~~Alice: I live in Boston, the city is great for museums.~~ (written by agent_0)
    - ~~Alice: I work at Acme Corp, the company makes robotics.~~ (written by agent_0)
    - ~~Bob: I adopted a puppy named Max, my first pet.~~ (written by agent_0)
    - ~~Bob: I am studying biology at Harvard.~~ (written by agent_0)
    - ~~Carol: I love hiking on weekends.~~ (written by agent_1)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by agent_1)
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by agent_1)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by agent_1)
    - ~~Alice: My favorite hobby is painting landscapes.~~ (written by agent_2)
    - ~~Bob: The weather has been rainy lately.~~ (written by agent_2)
    - ~~Alice: I started learning Spanish this month.~~ (written by agent_2)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by agent_0)
    - ~~Carol: I adopted a kitten named Whiskers, my first pet.~~ (written by agent_0)
    - ~~Bob: My puppy Max learned to fetch.~~ (written by agent_1)
    - ~~Alice: I moved to Seattle recently and I live downtown.~~ (written by agent_1)
    - ~~Alice: I now work at Globex Industries.~~ (written by agent_1)
    - ~~Dan: I just moved to Denver and I live near the mountains.~~ (written by agent_2)
    - ~~Carol: Work at Initech has been stressful lately.~~ (written by agent_2)
    - ~~Alice: The coffee shops in my new neighborhood are amazing.~~ (written by agent_0)
- **superseded facts** (3):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__P1.graph.html` · data: `graphs/shared__P1.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P2
policy `P2` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 23 · pruned: 5 · write rejections: 0 · superseded still visible: 0
- **pruned fact text** (5):
    - ~~Alice: I live in Boston, the city is great for museums.~~ (written by agent_0)
    - ~~Alice: I work at Acme Corp, the company makes robotics.~~ (written by agent_0)
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by agent_1)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by agent_1)
    - ~~Carol: Work at Initech has been stressful lately.~~ (written by agent_2)
- **superseded facts** (5):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__P2.graph.html` · data: `graphs/shared__P2.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P3
policy `P3` · model `-` · topology `shared`
- total facts ever written: 25
- active at end: 25 · pruned: 0 · write rejections: 3 · superseded still visible: 5
- **superseded facts** (5):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__P3.graph.html` · data: `graphs/shared__P3.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P4
policy `P4` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 25 · pruned: 3 · write rejections: 0 · superseded still visible: 5
- **pruned fact text** (3):
    - ~~Alice: My favorite hobby is painting landscapes.~~ (written by agent_0)
    - ~~Bob: I am studying biology at Harvard.~~ (written by agent_0)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by agent_1)
- **superseded facts** (5):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
    - Carol: Work at Initech has been stressful lately.  ->  invalidated at t=3888000
- interactive graph: `graphs/shared__P4.graph.html` · data: `graphs/shared__P4.graph.json` · communities: 4 · god nodes: alice, bob, carol

## shared__P5
policy `P5` · model `-` · topology `shared`
- total facts ever written: 28
- active at end: 11 · pruned: 17 · write rejections: 0 · superseded still visible: 1
- **pruned fact text** (17):
    - ~~Alice: My favorite hobby is painting landscapes.~~ (written by agent_0)
    - ~~Alice: I work at Acme Corp, the company makes robotics.~~ (written by agent_0)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by agent_1)
    - ~~Carol: I work at Initech, the company audits spreadsheets.~~ (written by agent_1)
    - ~~Dan: I live in Austin, the city has amazing tacos.~~ (written by agent_1)
    - ~~Bob: The weather has been rainy lately.~~ (written by agent_2)
    - ~~Alice: I started learning Spanish this month.~~ (written by agent_2)
    - ~~Dan: I play guitar in a local band, my favorite instrument.~~ (written by agent_0)
    - ~~Bob: My puppy Max learned to fetch.~~ (written by agent_1)
    - ~~Alice: I moved to Seattle recently and I live downtown.~~ (written by agent_1)
    - ~~Carol: Work at Initech has been stressful lately.~~ (written by agent_2)
    - ~~Alice: The coffee shops in my new neighborhood are amazing.~~ (written by agent_0)
    - ~~Bob: I visited my grandmother in Chicago last weekend.~~ (written by agent_0)
    - ~~Bob: I am studying biology at Harvard.~~ (written by agent_0)
    - ~~Dan: Denver winters are colder than expected.~~ (written by agent_1)
    - ~~Alice: I got promoted to senior engineer at Globex Industries.~~ (written by agent_2)
    - ~~Carol: My mentor at work is very supportive.~~ (written by agent_0)
- **superseded facts** (4):
    - Alice: I live in Boston, the city is great for museums.  ->  invalidated at t=2160000
    - Alice: I work at Acme Corp, the company makes robotics.  ->  invalidated at t=2160000
    - Carol: I work at Initech, the company audits spreadsheets.  ->  invalidated at t=2592000
    - Dan: I live in Austin, the city has amazing tacos.  ->  invalidated at t=2592000
- interactive graph: `graphs/shared__P5.graph.html` · data: `graphs/shared__P5.graph.json` · communities: 4 · god nodes: alice, bob, carol
