# Almanac key-gated context-sensor eval

model: google/gemini-2.5-flash
base anchors (2): ['festival:increase', 'weather:increase']
planted: ['festival:increase', 'weather:increase']
per-paraphrase jaccard: [1.0, 1.0]

| metric | value | bound | pass |
|---|---|---|---|
| planted-anchor recall | 1.00 | >= 0.5 | PASS |
| paraphrase jaccard (min) | 1.00 | >= 0.6 | PASS |

contract: contracts/context-sensor-stability.yaml (threshold 0.6)
