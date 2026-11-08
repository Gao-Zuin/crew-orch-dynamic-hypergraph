# Action-boundary evidence timeline

Run finished: True; truncated final line: False.

Rows show the latest environment-reported snapshot available at each after_action validator; snapshot event IDs expose older observations rather than asserting freshness. Missing fields remain unknown. Claims, map-cache cells and semantic completion are not inferred. Rewards use the original environment order.

| step | validator event | snapshot event | agent | issued action | position | resources | aboard | success | rewards |
|---:|---:|---:|---|---|---|---|---|---|---|
| 0 | 106 | 102 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [1681, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 0 | 106 | 103 | 7 | [1, 0, 0] | [54.0, 77.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [1681, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 204 | 198 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [3376, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 1 | 204 | 199 | 7 | [0, 13, 12] | [38.0, 51.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [3376, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 293 | 289 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5033, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 2 | 293 | 290 | 7 | [0, 13, 12] | [22.0, 26.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [5033, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 392 | 388 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5347, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 3 | 392 | 389 | 7 | [0, 13, 12] | [13.0, 12.0] | {"firefighters_carried": 5, "water": 0} | unknown | False | [5347, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| 4 | 463 | 459 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5347, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 4 | 463 | 460 | 7 | [3, 0, 0] | [13.0, 12.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [5347, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 5 | 538 | 534 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5358, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 5 | 538 | 535 | 7 | [0, 54, 77] | [29.0, 37.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [5358, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 642 | 638 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5371, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 6 | 642 | 639 | 7 | [0, 54, 77] | [45.0, 62.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [5371, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 739 | 733 | 6 | [0, 54.0, 77.0] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | False | False | [5387, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 7 | 739 | 734 | 7 | [0, 54, 77] | [54.0, 77.0] | {"firefighters_carried": 0, "water": 0} | unknown | False | [5387, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 824 | 820 | 6 | [0, 13, 12] | [54.0, 77.0] | {"civilian_carried": 0, "water": 0} | True | False | [5387, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 8 | 824 | 821 | 7 | [1, 0, 0] | [54.0, 77.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5387, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 918 | 914 | 6 | [0, 13, 12] | [38.0, 52.0] | {"civilian_carried": 0, "water": 0} | True | False | [5391, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 9 | 918 | 915 | 7 | [0, 13, 12] | [38.0, 52.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5391, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1012 | 1008 | 6 | [0, 38.0, 52.0] | [22.0, 27.0] | {"civilian_carried": 0, "water": 0} | True | False | [5395, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 10 | 1012 | 1009 | 7 | [0, 13, 12] | [22.0, 27.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5395, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 11 | 1108 | 1104 | 6 | [0, 22.0, 27.0] | [13.0, 12.0] | {"civilian_carried": 0, "water": 0} | True | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 11 | 1108 | 1105 | 7 | [0, 13, 12] | [13.0, 12.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 12 | 1215 | 1211 | 6 | [0, 13.0, 12.0] | [11.0, 14.0] | {"civilian_carried": 0, "water": 0} | True | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 12 | 1215 | 1212 | 7 | [0, 11, 14] | [11.0, 14.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 13 | 1322 | 1318 | 6 | [0, 11.0, 14.0] | [13.0, 12.0] | {"civilian_carried": 0, "water": 0} | True | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 13 | 1322 | 1319 | 7 | [0, 13, 12] | [13.0, 12.0] | {"firefighters_carried": 1, "water": 0} | unknown | False | [5397, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0] |
| 14 | 1419 | 1415 | 6 | [0, 13.0, 12.0] | [13.0, 12.0] | {"civilian_carried": 0, "water": 0} | False | True | [5397, 0, 0, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0] |
| 14 | 1419 | 1416 | 7 | [3, 0, 0] | [13.0, 12.0] | {"firefighters_carried": 0, "water": 0} | unknown | True | [5397, 0, 0, 0, 0, 0, 6, 0, 0, 0, 0, 0, 0] |
