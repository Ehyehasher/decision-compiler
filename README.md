# Decision compiler

Deterministic compiler for auditable trade studies. Weights must sum to 1. Scores are min-max normalized. A failed hard constraint excludes an option. A failed bias check or assumption blocks sign-off. A refresh keeps the prior package hash.

This is a demonstration fixture, not test data and not an award.

```bash
python3 compiler.py
python3 -m unittest test_compiler.py
```

Expected demo: diesel wins at a 400 km gate; hybrid wins after the gate rises to 550 km; the second package records the first hash.

## Paid work

Running this fixture is free. A custom episode is $49: your measures, constraints, and assumptions compiled into a sealed package and one refresh. Pay by X Money request to @wreckhavoc0 after you agree the handle, amount, and episode. No recovery claim. No award claim.

The same compiler is the demonstration shape for Army SBIR ARM26BX06-NV012, which closes 21 October 2026. Publishing this repo does not submit that proposal.
