# CLAUDE.md — src/config/contracts/

## Confirm the spec document before writing the reader

Before you write a new `FileContract` — and before you write its paired reader — declare
**which specification document is the data contract** (file / sheet / URL / version) and get
the owner's confirmation. This applies **per file**, including inside a batch of generated
sibling contracts: confirming one member of a batch does not confirm the rest.

**Why blocking, not advisory.** A source chosen silently poisons every column downstream, and
the reader stays perfectly self-consistent with the wrong document — the suite goes green
while the data is wrong, discovered only far from where the choice was made. Measured in
filings-b3: the owner had to interrupt mid-implementation, after **8 readers + 8 contracts**
were already derived from a document nobody had confirmed.

**Not decidable by a gate.** "Is this the right document" is a judgment call the owner makes,
not a mechanical check — there is no artifact a script can diff against before the contract
exists. What a gate *can* check is presence: did the author name a source at all. See
`example_source.py`'s docstring for where that's recorded; a contract lacking that line is a
process violation, not a runtime one, so it stays a review-time check rather than a pre-commit
gate — the register would still need a human to confirm the *content* is right.

**Where this sits relative to the rest of `config/CLAUDE.md`.** "Pin every contract to a
source-published oracle" (root doc) is the check that runs *after* the source is chosen —
generating `tuple_required` from real bytes so the contract can't drift from itself. This rule
is the gate *before* that one: it has no bytes to check yet, only a claim about which document
is authoritative. Skipping this step doesn't fail the oracle pin — it just pins the wrong
oracle, cleanly.
