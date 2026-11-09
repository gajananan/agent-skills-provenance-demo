#!/usr/bin/env python3
"""Show, in plain words, what a file's .bundle (its nono / Sigstore signature) says.

Usage, from run/workspace:  python3 ../../tools/show-bundle.py CLAUDE.md

Read-only. It decodes the bundle's signed statement (which file, which SHA-256,
which signer), recomputes the file's SHA-256 so you can see they match, and, if
the demo's keys are present, names the key whose fingerprint the bundle carries.
It does not verify the signature itself: `nono trust verify <file>` does that.
"""
import base64
import glob
import hashlib
import json
import os
import sys


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    path = sys.argv[1]
    bundle_path = path + ".bundle"
    if not os.path.isfile(bundle_path):
        print(f"{bundle_path}: no .bundle, so {path} is NOT signed")
        return 1

    bundle = json.load(open(bundle_path))
    env = bundle.get("dsseEnvelope", {})
    statement = json.loads(base64.b64decode(env.get("payload", "")))
    subject = (statement.get("subject") or [{}])[0]
    signed_sha = subject.get("digest", {}).get("sha256", "?")
    signer = statement.get("predicate", {}).get("signer", {})
    key_id = signer.get("key_id", "?")
    hint = bundle.get("verificationMaterial", {}).get("publicKey", {}).get("hint", "")
    sig = (env.get("signatures") or [{}])[0].get("sig", "")

    actual_sha = hashlib.sha256(open(path, "rb").read()).hexdigest()

    # Name the key behind the fingerprint, using the demo's public keys if present.
    keys_dir = os.path.join(os.path.dirname(os.path.abspath(path)), "..", "keys")
    for d in (keys_dir, os.path.join(os.getcwd(), "..", "keys")):
        for pub in glob.glob(os.path.join(d, "*.pub")):
            try:
                der = base64.b64decode(open(pub).read().strip())
            except Exception:
                continue
            if hashlib.sha256(der).hexdigest() == hint:
                hint_name = os.path.basename(pub)
                break
        else:
            continue
        break
    else:
        hint_name = "not one of the demo's keys"

    short = lambda s, n=16: s if len(s) <= 2 * n else f"{s[:n]}...{s[-8:]}"
    print(f"bundle      {bundle_path}  ({bundle.get('mediaType', '?').split('/')[-1]})")
    print(f"signs file  {subject.get('name', '?')}")
    print(f"signed hash sha256 {short(signed_sha)}")
    print(f"file now    sha256 {short(actual_sha)}  "
          + ("(MATCHES: unchanged since it was signed)" if actual_sha == signed_sha
             else "(DIFFERENT: the file changed after it was signed)"))
    print(f"signer      {os.path.basename(key_id)} ({signer.get('kind', '?')})")
    print(f"key         sha256 {short(hint)}  = {hint_name}")
    print(f"signature   {short(sig, 12)}  (ECDSA over the statement above)")
    return 0 if actual_sha == signed_sha else 1


if __name__ == "__main__":
    sys.exit(main())
