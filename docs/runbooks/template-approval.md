# Template Approval Runbook

1. Add the original or licensed template and its approved scene map under `content/templates/`.
2. Record the author, rights basis, license evidence, attribution, approval status, and any sponsorship disclosure in `content/template-manifest.csv`.
3. Require content and rights review before setting `approval_status` to `approved`.
4. Run `python content/templates/validate_manifest.py` and the test suite before merge.
5. Keep license evidence versioned; expired or missing evidence blocks deployment.

`mock-licensed` records are test fixtures only and must not be included in a production release manifest.
