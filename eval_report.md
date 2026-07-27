# Almanac Phase 1 eval report

synthetic store: 3 SKUs, 10 train weeks, 14 held-out days, planted stockout rate 0.1, fixed seeds

SKU-COLA-330: planted stockout days=8, repair MAPE=0.0612, forecast MAPE=0.0724, envelope point@0.90=867.0
SKU-BREAD-800: planted stockout days=6, repair MAPE=0.0904, forecast MAPE=0.0885, envelope point@0.90=343.7
SKU-ICE-500: planted stockout days=5, repair MAPE=0.0546, forecast MAPE=0.0979, envelope point@0.90=134.9

| metric | value | bound | pass |
|---|---|---|---|
| repair_mape | 0.0687 | <= 0.2 | PASS |
| forecast_mape | 0.0862 | <= 0.25 | PASS |
| envelope_monotonicity | 1.0000 | >= 1.0 | PASS |
| envelope_sanity | 1.0000 | >= 1.0 | PASS |
