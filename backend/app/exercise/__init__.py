"""Exercise and fitness module.

Independent of other health modules. It integrates by writing canonical
measurements through ``intelligence.ingest`` and reviewable rows through the
shared ``alerts`` table. Versioned payloads live in ``contracts``.
"""

CONTRACT_VERSION = "1.0.0"
DISCLAIMER = (
    "Demonstration example only. Not a medical device, flight rule, or exercise prescription. "
    "A crew medical officer must review anything flagged before it is used."
)
