# ADR 001: Deployment identities and least privilege

## Status

Accepted for implementation; grants are applied only after Lakebase and Unity Catalog resources exist.

## Decision

Story Engine uses separate Databricks and database identities:

| Identity | Purpose | Must not do |
| --- | --- | --- |
| CI deployer | Validate and deploy Declarative Automation Bundles | Read tenant application data or run application queries |
| Migration runner | Apply versioned Lakebase schema migrations | Serve HTTP requests or run generation jobs |
| App runtime | Serve authenticated API/SSE requests | Execute canonical writes directly or administer workspace resources |
| Job runtime | Run generation, reports, audit export, and quality jobs | Access another tenant outside the job's verified tenant context |
| World-command service role | Execute the narrowly scoped canonical commit function | Read/write unmanaged workspace resources |
| Administrator | Provision workspace infrastructure and emergency support | Be used for normal application traffic |

The FastAPI application validates Databricks Apps identity before setting the transaction-local tenant context. PostgreSQL row-level security remains mandatory; application checks are not a replacement for RLS.

## Consequences

- Runtime credentials are resource-bound/injected and never committed to source.
- Database owner credentials are excluded from App and Job environments.
- All production grants are reviewed in `resources/permissions.yml` and tested with negative authorization checks.

