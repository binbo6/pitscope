# Contributing

Use Python 3.11 or later. Install `requirements-dev.txt` in a virtual environment and run `python -m unittest discover -s tests -v`.

Keep examples synthetic and reproducible. Do not commit API keys, uploaded documents, SQLite databases, local paths, or project-specific reports. New engineering metrics should identify their region, direction, units, baseline, and source; missing input must remain explicit.

For retrieval changes, describe the affected query and evidence behavior. For reporting changes, validate at least Markdown, DOCX, and PDF. Do not claim retrieval or engineering accuracy improvements without an evaluation set and measured results.

Open an issue with a minimal synthetic example before proposing a large dependency or workflow expansion. Pull requests should explain the observable behavior and relevant verification.
