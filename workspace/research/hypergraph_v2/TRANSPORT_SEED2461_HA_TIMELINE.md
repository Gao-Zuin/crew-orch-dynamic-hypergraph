# Action-boundary evidence timeline

Run finished: True; truncated final line: False.

Rows show the latest environment-reported snapshot available at each after_action validator; snapshot event IDs expose older observations rather than asserting freshness. Missing fields remain unknown. Claims, map-cache cells and semantic completion are not inferred. Rewards use the original environment order.

| step | validator event | snapshot event | agent | issued action | position | resources | aboard | success | rewards |
|---:|---:|---:|---|---|---|---|---|---|---|
| 0 | 115 | 111 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 0 | 115 | 112 | 7 | [1, 0, 0] | [42.0, 82.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 214 | 208 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [3260, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 214 | 209 | 7 | [0, 84, 40] | [63.0, 61.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [3260, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 321 | 317 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4739, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 321 | 318 | 7 | [0, 84, 40] | [84.0, 40.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [4739, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 436 | 432 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4753, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 436 | 433 | 7 | [0, 42, 82] | [63.0, 61.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [4753, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 4 | 573 | 569 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4753, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 4 | 573 | 570 | 7 | [0, 84, 40] | [84.0, 40.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [4753, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 5 | 692 | 688 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 5 | 692 | 689 | 7 | [3, 0, 0] | [84.0, 40.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 815 | 811 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 815 | 812 | 7 | [0, 42, 82] | [63.0, 61.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 931 | 925 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 931 | 926 | 7 | [0, 42, 82] | [42.0, 82.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 1061 | 1057 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | True | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 1061 | 1058 | 7 | [1, 0, 0] | [42.0, 82.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 1198 | 1194 | 6 | [0, 42.0, 82.0] | [63.0, 61.0] | {"civilian_carried": 0, "water": 0} | True | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 1198 | 1195 | 7 | [0, 84, 40] | [63.0, 61.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1311 | 1307 | 6 | [0, 63.0, 61.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1311 | 1308 | 7 | [0, 84, 40] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4764, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 11 | 1428 | 1424 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | False | True | [4764, 0, 0, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0] |
| 11 | 1428 | 1425 | 7 | [3, 0, 0] | [84.0, 40.0] | {"firefighters_carried": 0, "water": 0} | unknown | True | [4764, 0, 0, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0] |
