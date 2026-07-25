# ADR 003: Versioned Template Rights Evidence

## Status

Accepted.

## Decision

Every template is an explicit manifest record with author, rights basis, evidence path,
source attribution, approval status, approved scene map, and sponsorship disclosure. The
validator blocks missing evidence and undeclared sponsored content. Mock licensed records
are permitted only as automated-test fixtures and must be replaced or removed for a
production release.
