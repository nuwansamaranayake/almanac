# Almanac — Risk Register

Living register for a probabilistic system. Each risk has an owner, a concrete tripwire (an
observable signal that says the mitigation has failed), and a status. Seeded from the chapter's
failure modes; extended as the system meets real data.

| Risk | Owner | Tripwire | Status |
|---|---|---|---|
| The Signal Scout hallucinates an event that never happened (fabricated festival, misdated closure) and, if confirmed, biases a live order. Mitigations: mandatory checkable provenance, deterministic calendar and geo validation, owner confirmation, and quarantine until backtested. | eng lead | A signal reaches the owner-confirmation queue whose `provenance.source` fails to fetch, or whose date/geo fields fail deterministic validation, or a promoted signal class is later traced to an event with no verifiable source. | open |
| Backtest overfitting promotes noise: a signal class earns live influence on spurious lift and then quietly degrades forecasts. Mitigations: promotion requires sustained lift across rolling windows and a minimum event count; demotion on decay is automatic. | eng lead | A signal class promoted to live influence shows negative marginal WAPE lift on the two most recent rolling backtest windows, or was promoted on fewer than the minimum event count. | open |
