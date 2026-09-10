# Findings and experiment archive

Keep successful and failed experiments here. Use one Markdown file per coherent
experiment and store large raw captures outside Git with a checked-in manifest
containing their filename, SHA-256, location/access constraints, and retention
plan. Small serial logs may be committed after secrets and unique identifiers are
redacted.

Every record should contain:

- date, author, device pseudonym, and board revision;
- exact repository/OpenWrt commits and artifact checksum;
- question or hypothesis;
- wiring, commands, configuration, and starting state;
- complete relevant output or a content-addressed reference to it;
- expected versus observed result;
- interpretation, confidence, and competing explanations;
- whether persistent state changed and how it was recovered;
- next experiment or the decision supported by the evidence.

Do not “clean up” historical failures after finding a workaround. Add a dated
follow-up and cross-link both records so future maintainers can distinguish a
disproved idea from an untested one.
