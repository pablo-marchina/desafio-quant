from __future__ import annotations

import pass_a_full_superset_audit as audit

# Engineering-only normalization: every spec is conceptually
# (profile, status, role, redundancy, hyper_override, time_override, justification, next_step).
# A tuple that omitted the optional time_override is expanded with None.
for technique, spec in list(audit.SPECS.items()):
    if len(spec) == 7:
        audit.SPECS[technique] = spec[:5] + (None,) + spec[5:]
    elif len(spec) != 8:
        raise RuntimeError(f"Unexpected spec arity for {technique}: {len(spec)}")

if __name__ == "__main__":
    audit.main()
