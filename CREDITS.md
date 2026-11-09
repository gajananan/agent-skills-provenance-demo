# Credits and acknowledgments (v5.0)

This demo and talk stand on open-source work. Each project is used under its own
license; see the linked repository.

## Core tool
- **nono**: the sandbox and Sigstore-based instruction-file signing shown
  throughout. https://github.com/always-further/nono (upstream:
  https://github.com/nolabs-ai/nono). Tested against nono 0.80.0. nono is from
  Always Further; its founder, Luke Hinds, co-created Sigstore.

## Underlying technology
- **Sigstore**: keyless signing, Fulcio (CA) and Rekor (transparency log).
  https://www.sigstore.dev / https://github.com/sigstore
- **Landlock** (Linux) and **Seatbelt / sandbox_init** (macOS): the kernel
  mechanisms nono uses to enforce the sandbox.

## Demo and recording
- **asciinema**: terminal recording. https://github.com/asciinema/asciinema
- **agg**: asciinema cast to GIF. https://github.com/asciinema/agg
- **Python** (https://www.python.org) and **Rust / Cargo**
  (https://www.rust-lang.org).

## Research cited
- **Snyk, "ToxicSkills"** (5 Feb 2026 dataset).
  https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub
- **Signals Corps**, "ClawHub skills after ClawHavoc" (22 Sep 2026).
  https://www.signalscorps.com/blog/clawhub-agent-skills-security-scan/
- **OWASP Agentic Skills Top 10.**
  https://owasp.github.io/www-project-agentic-skills-top-10
- **NVIDIA Verified Agent Skills** (May 2026) and **OpenSSF Model Signing**.
- **Cloud Security Alliance** notes on SKILL.md context poisoning and MCP.

All product names, logos and brands are the property of their respective owners.
Nothing here implies endorsement by any of the projects above.
