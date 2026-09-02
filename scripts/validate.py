#!/usr/bin/env python3
"""Validate the .moqtrace corpus against its manifest.

Checks:
1. manifest.json parses and every case directory on disk has an entry, and
   every entry a directory
2. Every file a case lists exists, and its `bytes` matches the file on disk
3. Every .moqtrace file on disk is listed by its case
4. Every file begins with the format preamble: "MOQTRACE", a declared version
   matching the case, and a header length that fits inside the file

Deliberately dependency-free, and therefore deliberately shallow: it reads the
preamble and the file sizes, not the CBOR. What a case *contains* is checked by
the two implementations that read it, which is the only check that means
anything — this one catches the manifest and the bytes disagreeing about which
files exist, which is what happens when a generator is run and the index is
not.
"""

import json
import os
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(REPO_ROOT, "moqtrace")
MANIFEST = os.path.join(CORPUS, "manifest.json")

MAGIC = b"MOQTRACE"
PREAMBLE_SIZE = 16  # 8 magic + 4 version + 4 header length

errors = []


def err(msg):
    errors.append(msg)
    print(f"  FAIL: {msg}", file=sys.stderr)


def check_preamble(path, rel, expected_version):
    """The first 16 bytes: magic, declared version, header length."""
    size = os.path.getsize(path)
    if size < PREAMBLE_SIZE:
        err(f"{rel}: {size} bytes, too short to hold a preamble")
        return

    with open(path, "rb") as handle:
        preamble = handle.read(PREAMBLE_SIZE)

    if preamble[:8] != MAGIC:
        err(f"{rel}: does not begin with {MAGIC.decode()}")
        return

    version, header_length = struct.unpack_from("<II", preamble, 8)
    if version != expected_version:
        err(f"{rel}: declares version {version}, manifest says {expected_version}")
    if PREAMBLE_SIZE + header_length > size:
        err(
            f"{rel}: header length {header_length} runs past the end of a "
            f"{size}-byte file"
        )


def main():
    print("Validating the .moqtrace corpus...\n")

    if not os.path.isdir(CORPUS):
        err("moqtrace/ does not exist")
        return 1

    with open(MANIFEST, encoding="utf-8") as handle:
        manifest = json.load(handle)

    cases = {case["id"]: case for case in manifest["cases"]}
    if len(cases) != len(manifest["cases"]):
        err("manifest.json lists a case id twice")

    on_disk = {
        name
        for name in os.listdir(CORPUS)
        if os.path.isdir(os.path.join(CORPUS, name))
    }

    print("Checking cases against directories...")
    for missing in sorted(on_disk - cases.keys()):
        err(f"moqtrace/{missing}/ has no manifest entry")
    for missing in sorted(cases.keys() - on_disk):
        err(f"manifest.json indexes '{missing}', which has no directory")

    print("Checking files against the manifest...")
    for case_id in sorted(cases.keys() & on_disk):
        case = cases[case_id]
        directory = os.path.join(CORPUS, case_id)
        listed = {entry["name"]: entry for entry in case["files"]}
        present = {
            name for name in os.listdir(directory) if name.endswith(".moqtrace")
        }

        for name in sorted(present - listed.keys()):
            err(f"moqtrace/{case_id}/{name} is not listed by its case")
        for name in sorted(listed.keys() - present):
            err(f"manifest.json lists moqtrace/{case_id}/{name}, which is absent")

        for name in sorted(listed.keys() & present):
            rel = f"moqtrace/{case_id}/{name}"
            path = os.path.join(directory, name)
            size = os.path.getsize(path)
            if size != listed[name]["bytes"]:
                err(f"{rel}: {size} bytes on disk, manifest says {listed[name]['bytes']}")
            check_preamble(path, rel, case["version"])

        for name in sorted(present):
            if not os.path.getsize(os.path.join(directory, name)):
                err(f"moqtrace/{case_id}/{name} is empty")

    print()
    if errors:
        print(f"FAILED: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"PASSED: {len(cases)} cases, all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
