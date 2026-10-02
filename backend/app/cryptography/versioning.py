"""Version declarations for exported SentinelCrypt evidence and artifacts."""

EVIDENCE_FORMAT_VERSION = 2
CRYPTOGRAPHIC_PROTOCOL_VERSION = 1
SCHEMA_VERSION = 1
EXPERIMENT_SCHEMA_VERSION = 1
RESEARCH_ARTIFACT_VERSION = 1

SUPPORTED_EVIDENCE_FORMAT_VERSIONS = frozenset({1, EVIDENCE_FORMAT_VERSION})
SUPPORTED_CRYPTOGRAPHIC_PROTOCOL_VERSIONS = frozenset(
    {CRYPTOGRAPHIC_PROTOCOL_VERSION}
)
SUPPORTED_SCHEMA_VERSIONS = frozenset({SCHEMA_VERSION})
SUPPORTED_EXPERIMENT_SCHEMA_VERSIONS = frozenset({EXPERIMENT_SCHEMA_VERSION})
SUPPORTED_RESEARCH_ARTIFACT_VERSIONS = frozenset({RESEARCH_ARTIFACT_VERSION})


def version_metadata() -> dict[str, int]:
    """Return the version identifiers that describe a current evidence package."""
    return {
        "evidence_format_version": EVIDENCE_FORMAT_VERSION,
        "protocol_version": CRYPTOGRAPHIC_PROTOCOL_VERSION,
        "schema_version": SCHEMA_VERSION,
        "experiment_schema_version": EXPERIMENT_SCHEMA_VERSION,
        "research_artifact_version": RESEARCH_ARTIFACT_VERSION,
    }
