"""Suite-wide fixtures. The report-id pseudonymiser runs in IDENTITY mode under
the tests (core/pseudonym.py): the synthetic corpora assert on their own ids
(1001, 1015, ...), and the mapping itself is tested in test_pseudonym.py."""
import os

os.environ.setdefault("MEDTEMPO_PSEUDONYM_KEY", "identity")
