# W4-R — Family expansion research

**Status:** outcome-blind research candidates only. The original W4-BER-v1.0 family dictionary is immutable.

To maximize independent event N, W4-R now separates **family expansion** from the original 15-family census. New families may be studied only through a new preregistration selected from recurrence, prediction-venue coverage, official PIT truth, economic asset mapping, historical depth and reproducibility — never from realized linked-asset returns.

## Highest-priority additions

### P0 — already supported by an event venue

- **Housing Starts:** ForecastEx has a recurring US Housing Starts product; Census publishes the monthly New Residential Construction release, scheduled release times and long historical series.
- **Building Permits:** ForecastEx lists US Building Permits; Census provides preliminary permits in the same recurring release plus revised permit history.

These are the cleanest immediate family-expansion candidates because both prediction-market coverage and official truth already have primary-source evidence.

## P1 — potentially high marginal N

- **Durable Goods** — monthly Census release.
- **New Home Sales** — monthly Census release.
- **US Trade Balance** — monthly Census/BEA release.
- **PPI** — monthly BLS release.
- **JOLTS** — monthly BLS release.
- **Industrial Production** — monthly Federal Reserve release.
- **EIA Crude Inventories** — weekly WPSR, normally Wednesday 10:30 ET.
- **EIA Natural Gas Storage** — weekly WNGSR, normally Thursday 10:30 ET.
- **USDA WASDE** — monthly 12:00 ET scheduled release with archive back to 1973.

The EIA families are especially attractive because weekly recurrence could add many independent dates if prediction-venue coverage exists. WASDE could extend ARGOS into commodities, which is allowed by the challenge, but it still needs prediction-market coverage proof.

## P2

Non-US central-bank decisions are a separate high-N route for FX/rates/equity-index responses, but each bank needs its own official-truth and venue-coverage gate.

## Revision-aware support

FRED/ALFRED exposes real-time periods and vintage dates. It should be used to audit revisions and reconstruct what was known when, while source-agency release documents remain primary truth where available.

## Admission gate

No new family can reach the W4 outcome freeze until it has:

1. a separately frozen family dictionary;
2. population-scale venue coverage;
3. official PIT release truth;
4. frozen `canonical_event_id` rules;
5. frozen economically justified linked-asset mapping class;
6. measured pre-event prediction-market history;
7. marginal independent N after cross-family/cross-venue deduplication.

Multiple thresholds, headline/core values or multiple assets from the same release never automatically increase independent event N.

Machine-readable authority: `../registry/w4_family_expansion_research_v1.json`.
