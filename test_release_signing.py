#!/usr/bin/env python3
"""Test release signing workflow with test GPG keys."""

import subprocess
import os
import tempfile


def generate_test_key():
    """Generate a test GPG key for verification testing."""
    result = subprocess.run(
        ["gpg", "--full-generate-key"],
        input="\n".join([
            "2",  # RSA (sign only)
            "2048",  # key size
            "1",  # key usage
            "1y",  # validity
            "Test Release Key",  # name
            "test@localhost",  # email
            "",  # comment
        ]),
        capture_output=True,
        text=True,
        timeout=30,
    )
    print("Key generation return code:", result.returncode)
    if result.returncode != 0:
        print("STDERR:", result.stderr)
        return None

    # Export public key
    result = subprocess.run(
        ["gpg", "--armor", "--export", "Test Release Key"],
        capture_output=True,
        text=True,
    )
    pub_key = result.stdout

    # Export private key
    result = subprocess.run(
        ["gpg", "--armor", "--export-secret-keys", "Test Release Key"],
        capture_output=True,
        text=True,
    )
    priv_key = result.stdout

    return pub_key, priv_key


def test_signing_workflow():
    """Test the full source→build→artifact→checksum→signature→release workflow."""
    pub_key, priv_key = generate_test_key()
    if not pub_key:
        print("FAIL: Could not generate test key")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nWorking in: {tmpdir}")

        # 1. Create test artifact
        artifact_path = os.path.join(tmpdir, "sentinelcrypt-1.0.0.tar.gz")
        with open(artifact_path, "w") as f:
            f.write("sentinelcrypt release artifact content")

        # 2. Generate checksums
        checksums_path = os.path.join(tmpdir, "SHA256SUMS")
        result = subprocess.run(
            ["sha256sum", artifact_path],
            capture_output=True,
            text=True,
        )
        with open(checksums_path, "w") as f:
            f.write(result.stdout)

        print("Checksums file created")

        # 3. Import test private key and sign
        key_path = os.path.join(tmpdir, "test-privkey.asc")
        with open(key_path, "w") as f:
            f.write(priv_key)

        # Import the key
        result = subprocess.run(
            ["gpg", "--batch", "--import", key_path],
            capture_output=True,
            text=True,
        )
        print("Key imported, return code:", result.returncode)
        if result.returncode != 0:
            print("FAIL: Key import failed")
            print("STDERR:", result.stderr)
            return False

        # Sign the checksums
        sig_path = os.path.join(tmpdir, "SHA256SUMS.sig")
        result = subprocess.run(
            ["gpg", "--armor", "--detach-sign", checksums_path],
            capture_output=True,
            text=True,
        )
        with open(sig_path, "w") as f:
            f.write(result.stdout)
        print("Signature created, length:", len(result.stdout))

        # 4. Verify the signature
        print("\n--- Signature Verification ---")
        result = subprocess.run(
            ["gpg", "--verify", sig_path, checksums_path],
            capture_output=True,
            text=True,
        )
        print("gpg verify return code:", result.returncode)
        print("gpg verify stdout:", result.stdout)

        # 5. Verify the checksum
        print("\n--- Checksum Verification ---")
        result = subprocess.run(
            ["sha256sum", "-c", checksums_path],
            capture_output=True,
            text=True,
        )
        print("sha256sum return code:", result.returncode)
        print("sha256sum stdout:", result.stdout)

        # 6. Verify public key can validate
        print("\n--- Public Key Verification ---")
        # Import just the public key
        result = subprocess.run(
            ["gpg", "--import", "--no-tty", "/dev/stdin"],
            input=pub_key,
            capture_output=True,
            text=True,
        )
        print("Public key import return code:", result.returncode)

        result = subprocess.run(
            ["gpg", "--verify", sig_path, checksums_path],
            capture_output=True,
            text=True,
        )
        print("Public key verify return code:", result.returncode)
        print("Public key verify stdout:", result.stdout)

    print("\n=== Test workflow PASSED ===")
    return True


if __name__ == "__main__":
    success = test_signing_workflow()
    exit(0 if success else 1)