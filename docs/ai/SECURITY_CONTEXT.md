# SentinelCrypt AI — Security Context

## Cryptographic Principles
1. **Canonical JSON Serialization:**
   - Keys sorted lexicographically.
   - Zero extraneous whitespaces (`separators=(',', ':')`).
   - Floats rounded or formatted deterministically.
   - ISO-8601 UTC timestamp format (`YYYY-MM-DDTHH:MM:SS.ffffffZ`).
   - Standard UTF-8 encoding.

2. **Hash Chain Construction:**
   - **Payload Hash:** `SHA-256(canonical_payload_bytes)`
   - **Record Hash:** `SHA-256(previous_hash + payload_hash + timestamp + sequence_number)`
   - **Genesis Record:** `previous_hash = "0" * 64` (64 zeros).

3. **Tamper Evidence & Non-Repudiation:**
   - Any alteration to `canonical_payload` changes `payload_hash`, which breaks `record_hash`.
   - Any alteration to `record_hash` breaks the `previous_hash` of the subsequent record.
   - Verification detects the exact corrupted sequence number.

4. **Threat Model Coverage:**
   - Adversarial inference manipulation (detected via hash chain mismatch).
   - Log injection and deletion (detected via broken sequence numbers and hash pointers).
   - Model inversion / poisoning (bounded by dataset SHA-256 checksums and immutable training records).
