#!/usr/bin/env python3
"""Engineering-only runner for the frozen EUAS census classifier.

The first workflow proved Gamma returned 100 events/page and exceeded the
original conservative 300-page guard. This runner changes only the pagination
safety ceiling; classifier rules, EUAS weights and scientific boundaries stay
unchanged.
"""
import wave1_event_universe_contract_census as census

census.MAX_PAGES = 2000
census.API_LIMIT = 500

if __name__ == "__main__":
    census.main()
