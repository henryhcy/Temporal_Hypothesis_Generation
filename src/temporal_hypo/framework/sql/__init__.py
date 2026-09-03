"""Stage 2: retrieval over the narrative-free eval DB (``data/medtempo_eval.db``).

- ``views.sql`` / ``build_eval_db.py`` -- the DDL models see, and the builder
- ``executor.py``  -- read-only sandboxed execution
- ``aggregate.py`` -- the per-arm row contract and ``ArmRows -> ArmCounts``
- ``compiler.py``  -- reference SQL per mode (the retrieval upper bound)
- ``llm_sql.py``   -- a model writes the SQL instead
"""
