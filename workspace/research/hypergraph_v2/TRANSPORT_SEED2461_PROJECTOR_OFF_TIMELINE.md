# Action-boundary evidence timeline

Run finished: True; truncated final line: False.

Rows show the latest environment-reported snapshot available at each after_action validator; snapshot event IDs expose older observations rather than asserting freshness. Missing fields remain unknown. Claims, map-cache cells and semantic completion are not inferred. Rewards use the original environment order.

| step | validator event | snapshot event | agent | issued action | position | resources | aboard | success | rewards |
|---:|---:|---:|---|---|---|---|---|---|---|
| 0 | 98 | 94 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 0 | 98 | 95 | 7 | [1, 0, 0] | [42.0, 82.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 193 | 189 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 193 | 190 | 7 | [1, 0, 0] | [42.0, 82.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [1558, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 308 | 302 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [3258, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 308 | 303 | 7 | [0, 84, 40] | [63.0, 61.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [3258, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 410 | 406 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4740, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 410 | 407 | 7 | [0, 84, 40] | [84.0, 40.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [4740, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 4 | 509 | 505 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4740, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 4 | 509 | 506 | 7 | [3, 0, 0] | [84.0, 40.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4740, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 5 | 609 | 605 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 5 | 609 | 606 | 7 | [0, 42, 82] | [63.0, 61.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4753, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 697 | 691 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | False | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 697 | 692 | 7 | [0, 42, 82] | [42.0, 82.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 801 | 797 | 6 | [0, 42.0, 82.0] | [42.0, 82.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 801 | 798 | 7 | [1, 0, 0] | [42.0, 82.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 904 | 900 | 6 | [0, 42.0, 82.0] | [63.0, 61.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 904 | 901 | 7 | [0, 84, 40] | [63.0, 61.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 1007 | 1003 | 6 | [0, 63.0, 61.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 1007 | 1004 | 7 | [0, 84, 40] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1110 | 1106 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1110 | 1107 | 7 | [0, 84.0, 40.0] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 11 | 1215 | 1211 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 11 | 1215 | 1212 | 7 | [0, 84.0, 40.0] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 12 | 1320 | 1316 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 12 | 1320 | 1317 | 7 | [0, 84.0, 40.0] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 13 | 1418 | 1414 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 13 | 1418 | 1415 | 7 | [0, 84.0, 40.0] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 14 | 1516 | 1512 | 6 | [0, 84.0, 40.0] | [84.0, 40.0] | {"civilian_carried": 0, "water": 0} | True | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 14 | 1516 | 1513 | 7 | [0, 84.0, 40.0] | [84.0, 40.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [4765, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
