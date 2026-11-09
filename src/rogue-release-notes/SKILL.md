---
name: release-notes
description: Draft release notes. (Demo: this fixture is CORRECTLY SIGNED, but by an UNTRUSTED key.)
---

# Release notes (rogue fixture)

This skill is a valid, correctly-signed skill, signed with a DIFFERENT key that
the trust policy does not list as a trusted publisher. Its content is harmless.
The point of this case: a good signature is not enough. The policy decides WHOSE
signatures to trust, so an attacker signing their own skill with their own key is
rejected because that key is not a trusted publisher.
