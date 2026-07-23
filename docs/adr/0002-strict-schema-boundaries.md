# ADR 0002: Strict Schema Boundaries

## Status

Accepted for the core configuration and storage schemas task.

## Context

Phase 1 stores required equipment and zone configuration in Home Assistant
config-entry data and config-subentry data, observation preferences in
config-entry options, and nonauthoritative restart/history data in a versioned
runtime Store document.

The Phase 1 technical design defines explicit JSON shapes for those documents
but does not define an extension bucket for unknown fields.

## Decision

Schema decoding rejects unknown persisted fields at every object boundary.
Decoded data is converted into frozen typed models, and encoding emits only the
current documented JSON-compatible fields.

The implementation uses standard-library dataclasses, enums, and explicit
decode/encode helpers rather than a schema framework dependency.

## Consequences

Unknown fields cannot be silently discarded or accidentally carried into future
runtime behavior.

Future schema changes must add a documented field and, when needed, an explicit
migration path before persisted data with that field is accepted.

Runtime Store data remains nonauthoritative. Unsupported future Store versions
or undocumented historical versions are rejected by the schema layer so the
future runtime can rebuild live observation state instead of trusting ambiguous
persisted data.
