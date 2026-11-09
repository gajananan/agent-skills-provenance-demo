#!/usr/bin/env python3
"""The real agent: a minimal, provider-agnostic loop with a LIVE model in it.

nono verifies every covered file (CLAUDE.md, the skills, the inventory) BEFORE
this process starts, so the instructions the model reads are exactly what the
publisher signed. If a covered file was tampered with, nono refuses to launch
this process at all, and the model is never called.

What the agent does:
  1. reads the verified ground rules (CLAUDE.md) and every verified skill
     (.claude/skills/*/SKILL.md);
  2. sends them, plus the task, to the model and asks for ONE command;
  3. runs that command only if it EXACTLY matches (parsed argv, not a substring)
     a command that one of the verified skills documents. The allowlist comes
     from the signed skills themselves;
  4. prints a run marker, so the demo can assert that it really executed.

Config via environment:
  AGENT_PROVIDER    'openai' (any OpenAI-compatible API, the default) or 'anthropic'
  AGENT_API_BASE    e.g. http://localhost:11434 (Ollama), https://api.groq.com/openai
  AGENT_API_KEY     the API key (for Ollama, any non-empty value)
  AGENT_MODEL       model id, e.g. llama3.1
  AGENT_TASK        the task for the model (the demo sets one per beat)
  AGENT_STUB_SKILL  stub mode only: which skill's documented command to reply with
  NONO_DEMO_STUB=1  offline rehearsal: no model call, a deterministic reply

Exit codes: the skill's own exit code when it ran; 2 no usable skill; 3 the
model's reply is not a command any verified skill documents; 6 the model API
failed. All demo payloads are benign.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

RUN_MARKER = os.environ.get("DEMO_RUN_MARKER", "WRAPPED_PROCESS_RAN")
DEFAULT_TASK = "Give an overview of what this repository contains."


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def discover_skills():
    """Return [(name, path, text, documented_argv)] for each skill that documents a command."""
    skills = []
    for path in sorted(glob.glob(".claude/skills/*/SKILL.md")):
        text = read(path)
        name_m = re.search(r"^name:\s*(.+?)\s*$", text, re.MULTILINE)
        cmd_m = re.search(r"`([^`]*scripts/[^`]+\.py)`", text)
        if not (name_m and cmd_m):
            continue
        try:
            argv = shlex.split(cmd_m.group(1).strip())
        except ValueError:
            continue
        skills.append((name_m.group(1).strip(), path, text, argv))
    return skills


def model_endpoint():
    provider = os.environ.get("AGENT_PROVIDER", "openai").lower()
    default_base = "https://api.anthropic.com" if provider == "anthropic" else "https://api.openai.com"
    base = os.environ.get("AGENT_API_BASE", default_base).rstrip("/")
    path = "/v1/messages" if provider == "anthropic" else "/v1/chat/completions"
    return provider, base + path


def ask_model(system, user):
    provider, url = model_endpoint()
    key = os.environ["AGENT_API_KEY"]
    default_model = "claude-3-5-haiku-latest" if provider == "anthropic" else "gpt-4o-mini"
    model = os.environ.get("AGENT_MODEL", default_model)
    if provider == "anthropic":
        body = {"model": model, "max_tokens": 200, "temperature": 0, "system": system,
                "messages": [{"role": "user", "content": user}]}
        headers = {"content-type": "application/json", "x-api-key": key,
                   "anthropic-version": "2023-06-01"}
    else:
        body = {"model": model, "max_tokens": 200, "temperature": 0,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        headers = {"content-type": "application/json", "authorization": "Bearer " + key}
    print(f"agent: asking the model ({model}) for one command ...")
    sys.stdout.flush()
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.load(resp)
    if provider == "anthropic":
        return "".join(b.get("text", "") for b in data.get("content", []))
    return data["choices"][0]["message"]["content"] or ""


def candidates(reply):
    """Each reply line as a possible command; tolerates a code fence, a leading
    '$ ' prompt and surrounding backticks. The exact-match check stays strict."""
    for line in reply.splitlines():
        line = line.strip()
        if not line or line.startswith("```"):
            continue
        line = re.sub(r"^\$\s*", "", line).strip().strip("`").strip()
        if line:
            yield line


def main():
    rules = read("CLAUDE.md")
    skills = discover_skills()
    if not skills:
        print("agent: no verified skill documents a command; refusing to guess.", file=sys.stderr)
        return 2
    print(f"agent: loaded the verified CLAUDE.md (ground rules) and {len(skills)} verified skill(s):")
    for name, _, text, argv in skills:
        desc_m = re.search(r"^description:\s*(.+?)\s*$", text, re.MULTILINE)
        desc = desc_m.group(1) if desc_m else ""
        print(f"agent:   - {name}: {desc.split('. ')[0].rstrip('.')}; runs `{shlex.join(argv)}`")
    allowed = {tuple(argv): name for name, _, _, argv in skills}
    task = os.environ.get("AGENT_TASK", DEFAULT_TASK)
    print(f"agent: task: {task}")

    if os.environ.get("NONO_DEMO_STUB") == "1" or not os.environ.get("AGENT_API_KEY"):
        want = os.environ.get("AGENT_STUB_SKILL", skills[0][0])
        match = next((s for s in skills if s[0] == want), skills[0])
        reply = shlex.join(match[3])
        print(f"agent: STUB mode, no model called; canned reply: {reply!r}")
    else:
        system = ("You are a repository agent. Obey the ground rules. Use only the provided skills. "
                  "Reply with ONLY the single shell command that the matching skill says to run, nothing else.")
        skill_text = "\n\n".join(f"--- skill: {n} ({p}) ---\n{t}" for n, p, t, _ in skills)
        user = f"Ground rules (CLAUDE.md):\n{rules}\n\nAvailable skills:\n{skill_text}\n\nTask: {task}"
        try:
            reply = ask_model(system, user).strip()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:200].replace("\n", " ")
            print(f"agent: model API error {e.code} from {e.url}: {detail}", file=sys.stderr)
            print("agent: hint: 404 = model not pulled or AGENT_MODEL mismatch; 401 = API key rejected", file=sys.stderr)
            return 6
        except (urllib.error.URLError, OSError) as e:
            print(f"agent: cannot reach the model at {model_endpoint()[1]}: {getattr(e, 'reason', e)}", file=sys.stderr)
            return 6
        print(f"agent: model replied: {reply[:120]!r}")

    chosen = None
    for line in candidates(reply):
        try:
            argv = tuple(shlex.split(line))
        except ValueError:
            continue
        if argv in allowed:
            chosen = argv
            break
    if chosen is None:
        print("agent: refusing; the reply is not exactly a command any verified skill documents.", file=sys.stderr)
        return 3

    skill = allowed[chosen]
    print(f"agent: {shlex.join(chosen)!r} exactly matches the command the verified '{skill}' skill documents")
    print("agent: running it inside the sandbox ...")
    sys.stdout.flush()
    cmd = [sys.executable] + list(chosen[1:]) if chosen[0] in ("python3", "python") else list(chosen)
    rc = subprocess.run(cmd).returncode
    print(f"{RUN_MARKER} runtime=real skill={skill} rc={rc}")
    print(f"agent: skill finished (rc={rc})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
