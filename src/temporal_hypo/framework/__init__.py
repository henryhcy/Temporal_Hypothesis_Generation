"""The model pipeline / eval harness (docs/plan/11_model_pipeline.md).

Stage contract::

    question row (INPUT_FIELDS only)
      -S1-> StructuredClaim            (framework.claim_schema; extract/*)
      -S2-> per-arm ArmRows            (framework.sql.*; aggregate -> ArmCounts)
      -S3-> Prediction                 (framework.run_test; reuses core.answers)
      -S4-> metrics                    (framework.evaluate)

Hard rules the harness enforces mechanically rather than by convention:

- It never opens ``data/medtempo.db`` (which carries ``reports.narrative``); it
  reads ``data/medtempo_eval.db`` built by ``sql/build_eval_db.py``.
- It never calls ``core.answers.compute_answer`` for an asserted claim; S3 goes
  through ``core_significance(core, named=...)`` so the named cell is honoured.
- It never reads the release field ``test_verdict`` (issue 25); the gold label is
  ``gold_verdict``.
"""
