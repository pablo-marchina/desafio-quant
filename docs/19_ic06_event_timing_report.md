# ARGOS — IC-06 Event Timing Data Gate

**Decision:** `PASS_DAILY_EVENT_TIMING_SESSION_TIMING_LIMITED`

IC-06 prepares timing fields for the later implementation audit. It does not infer event-session labels from weak proxies.

## Daily timing

- frozen events: **117**
- daily safe cutoffs independently validated against XNYS prior close: **117/117**
- evidence composition in the frozen resolver audit: **80** high-confidence explicit datelines, **36** validated same-day earnings exhibits, **1** preserved official IR case
- SEC acceptance timestamp was never used as release time

The canonical daily field is `daily_safe_cutoff_utc`.

## Intraday / session timing

The legacy resolver preserved only **8** events with official exact time or explicit BMO/AMC session in its separate intraday/T0 panel. The identities/table of those 8 are not accessible through the currently connected canonical artifacts, so this data product deliberately does **not** guess them.

`release_session` is therefore `UNKNOWN_NOT_MATERIALIZED_FOR_THIS_EVENT` across the broad table. The known 8/117 coverage is recorded in the summary as a limitation.

For the future technique audit: daily/event-date techniques can use the 117/117 timing layer; techniques that require BMO/AMC or exact release time do not have broad-sample data and must be gated accordingly unless an explicit new collection is opened.
