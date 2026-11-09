# shellcheck shell=bash
# Shared helpers for the skill-provenance demo, v5.0.
# All state lives under ./run/ so nothing touches the presenter's real keychain,
# config, or home directory.

set -uo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$DEMO_DIR/src"
RUN_DIR="$DEMO_DIR/run"
WORK_DIR="$RUN_DIR/workspace"
KEYS_DIR="$RUN_DIR/keys"
TRUSTED_KEY="$KEYS_DIR/acme-platform-team.pem"     # the trusted publisher
ROGUE_KEY="$KEYS_DIR/rogue-publisher.pem"          # a valid key the policy does NOT trust
TRUSTED_REF="file://$TRUSTED_KEY"
ROGUE_REF="file://$ROGUE_KEY"
VAULT_FILE="$RUN_DIR/vault/placeholder.txt"        # OUTSIDE the workspace
INVENTORY_FILE=".nono-inventory"

# Policy include patterns are derived from artifact-spec.json (single source of
# truth). compute_includes() fills INCLUDES at setup, once the workspace exists.
INCLUDES=()

export XDG_CONFIG_HOME="$RUN_DIR/.config"          # keep trust config out of ~/.config
export NONO_DEMO_VAULT="$VAULT_FILE"
export NONO_THEME="${NONO_THEME:-minimal}"
export NONO_NO_UPDATE_CHECK=1
export NONO_NO_SAVE_PROMPT=1

# Marker the wrapped process prints when it actually executes.
export DEMO_RUN_MARKER="WRAPPED_PROCESS_RAN"

# Extra nono args a caller wants on the gate launch (e.g. --read, --allow-domain).
NONO_EXTRA=()

if { [ -t 1 ] || [ "${NONO_DEMO_COLOR:-0}" = "1" ]; } && [ -z "${NO_COLOR:-}" ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
  BLUE=$'\033[34m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; CYAN=$'\033[36m'
else
  BOLD=""; DIM=""; RESET=""; BLUE=""; GREEN=""; RED=""; YEL=""; CYAN=""
fi

banner() { echo; echo "${BOLD}${BLUE}============================================================${RESET}";
  echo "${BOLD}${BLUE}  $1${RESET}${BOLD} · $2${RESET}";
  echo "${BOLD}${BLUE}============================================================${RESET}"; echo; }
say()  { echo "${DIM}# $*${RESET}"; }
# pause() reads NONO_DEMO_AUTO from the environment directly, so `./demo.sh all`
# (which exports it) is reliably non-interactive.
pause(){ if [ "${NONO_DEMO_AUTO:-0}" = "1" ]; then sleep "${NONO_DEMO_SLEEP:-1.0}"; return; fi
  printf "%s" "${DIM}  (press Enter${1:+ $1})${RESET}"; read -r _ || true; }

# A labelled step inside a beat (beats 2 and 3: tamper, then verify).
step() { echo; echo "${BOLD}${YEL}>> $1${RESET}${2:+${DIM}  ($2)${RESET}}"; }

# Show an append on screen as a shell command, then perform it.
run_append() {  # <file> <line>
  echo "${BOLD}${CYAN}\$ echo '$2' >> $1${RESET}"; printf '%s\n' "$2" >> "$1"; }

run() { echo "${BOLD}${CYAN}\$ $*${RESET}"; "$@"; local rc=$?; echo "${DIM}  [exit $rc]${RESET}"; return $rc; }
# Like run, but prints the exit code only when it is not 0 (for cp, ls).
run_q() { echo "${BOLD}${CYAN}\$ $*${RESET}"; "$@"; local rc=$?; [ "$rc" -eq 0 ] || echo "${DIM}  [exit $rc]${RESET}"; return $rc; }

# Drop nono's post-run denial-advice footer so beat 6 reads cleanly.
_footer_filter() {
  awk '
    /likely sandbox-related access issue/ {skip=1}
    skip && /Query policy:/ {skip=0; next}
    /No path denials were observed/ {next}
    /failure may be unrelated to sandbox/ {next}
    !skip'
}

# ---- what the audience should notice ----------------------------------------
# Display only (the checks always read the raw output): shorten absolute paths to
# repo-relative ones, show a key by its file name, drop nono's three-line macOS
# note about glob includes (see "macOS" in the docs), and hide the run marker the
# checks look for (beat 7's nono-alone marker becomes a plain phrase). NONO_DEMO_VERBOSE=1 shows the raw output instead.
_esc() { printf '%s' "$1" | sed 's/[][\.*^$|]/\\&/g'; }
_tidy() {
  if [ "${NONO_DEMO_VERBOSE:-0}" = "1" ]; then cat; return; fi
  local w r; w="$(_esc "$WORK_DIR")"; r="$(_esc "$RUN_DIR")"
  sed -E \
      -e "s|file://[^ )]*/([^/ )]+)|\1|g" \
      -e "s|$w/||g" -e "s|$w|run/workspace|g" -e "s|$r/|../|g" \
      -e "/^${DEMO_RUN_MARKER} (runtime|skill)=/d" \
      -e "s|^${DEMO_RUN_MARKER} \\(nono alone, gate bypassed\\)|nono launched the process (gate bypassed)|" \
    | awk '/glob patterns in .includes. only match files present at startup/ {skip=3}
           skip > 0 {skip--; next} {print}' \
    | _compact
}

# Display only: in nono's trust scan, show every FAIL line but fold the PASS lines
# into one ("PASS  all 7 files (publisher: ...)"), drop nono's "Command exited with
# code N." (the demo prints [exit N]) and squeeze repeated blank lines.
_compact() {
  awk '
    function flush_pass(   pubs, k, line) {
      if (npass == 0) return
      pubs = ""; for (k in pub) pubs = pubs (pubs == "" ? "" : ", ") k
      line = (nfail == 0 ? "all " npass : "the other " npass) " file" (npass == 1 ? "" : "s")
      print "    PASS  " line " (publisher: " pubs ")"
      npass = 0; nfail = 0; for (k in pub) delete pub[k]
    }
    /Scanning [0-9]+ instruction file/ { inscan = 1; npass = 0; nfail = 0; print; next }
    inscan && /^ *PASS / {
      npass++
      if (match($0, /publisher: [^)]+/)) pub[substr($0, RSTART + 11, RLENGTH - 11)] = 1
      next
    }
    inscan && /^ *FAIL / { nfail++; print; next }
    inscan && /Trust scan:/ { flush_pass(); inscan = 0; print; next }
    inscan && /^ *$/ { next }
    /^Command exited with code [0-9]+\.$/ { next }
    /^ *$/ { if (blank) next; blank = 1; print; next }
    { blank = 0; print }'
}

# Raw tool output: lines that report a denial or a refusal are shown in red, a
# breach (something got through with no sandbox) in yellow.
_hl() {
  if [ -z "$RED" ]; then cat; return; fi
  awk -v r="$BOLD$RED" -v y="$BOLD$YEL" -v z="$RESET" '
    /NOT contained|status=breached/ {print y $0 z; next}
    /DENIED|Permission denied|Operation not permitted|untrusted signer|no \.bundle|FAILED|FAIL[ ,:]|Aborting|failed verification|does not match|^ *(modified|removed|added|special): |refusing/ {print r $0 z; next}
    {print}'
}

# The verdict of each step gets a box: red for a refusal or a denial, green for an
# allowed run, yellow for something that got through. Plain ASCII content only.
_cols() {
  local c; c="$(tput cols 2>/dev/null)"
  case "$c" in ''|*[!0-9]*) c=80 ;; esac
  [ "$c" -ge 40 ] || c=80
  echo "$c"
}
box() {  # <colour> <title> [line ...]   (long lines wrap inside the box)
  local col="$1" max=0 cap l w bar first=1
  shift
  for l in "$@"; do [ "${#l}" -gt "$max" ] && max=${#l}; done
  cap=$(( $(_cols) - 8 )); [ "$max" -gt "$cap" ] && max=$cap
  local -a out=()
  for l in "$@"; do
    if [ "${#l}" -le "$max" ]; then out+=( "$l" ); continue; fi
    local ind="${l%%[! ]*}"            # keep the line's indent on its continuation
    while IFS= read -r w; do out+=( "$w" ); done < <(printf '%s\n' "${l#"$ind"}" \
      | fold -s -w $(( max - ${#ind} - 2 )) | sed "1s/^/$ind/; 2,\$s/^/$ind  /")
  done
  bar="$(printf '%*s' $((max + 2)) '' | sed 's/ /─/g')"
  echo "${BOLD}${col}  ┌${bar}┐${RESET}"
  for l in "${out[@]}"; do
    if [ "$first" -eq 1 ]; then printf '%s  │ %-*s │%s\n' "$BOLD$col" "$max" "$l" "$RESET"; first=0
    else printf '%s  │%s %-*s %s│%s\n' "$BOLD$col" "$RESET$col" "$max" "$l" "$BOLD" "$RESET"; fi
  done
  echo "${BOLD}${col}  └${bar}┘${RESET}"
}

CAP=""
run_capture() {
  echo "${BOLD}${CYAN}\$ $*${RESET}"
  CAP="$("$@" 2>&1)"; local rc=$?
  printf '%s\n' "$CAP" | _footer_filter | _tidy | _hl
  echo "${DIM}  [exit $rc]${RESET}"
  return $rc
}

# Like run, with paths shortened and denial and refusal lines highlighted.
run_hl() {
  echo "${BOLD}${CYAN}\$ $*${RESET}"
  "$@" 2>&1 | _tidy | _hl; local rc=${PIPESTATUS[0]}
  echo "${DIM}  [exit $rc]${RESET}"
  return "$rc"
}

# The refusal box: the headline is the thing to notice, the agent never started.
# It names the check that refused, why, and the part of the launch that never ran.
refusal_box() {  # <check that refused> <command that was not run> [reason line ...]
  local check="$1" notrun="$2"; shift 2
  local tail="Nothing ran: no agent, no skill code."
  if type agent_is_real >/dev/null 2>&1 && agent_is_real; then
    tail="Nothing ran: no agent, no skill code, no model call."
  fi
  box "$RED" "LAUNCH REFUSED: THE AGENT NEVER STARTED" "  refused by: $check" "$@" \
    "  not run: $notrun" "  $tail"
}

# ---- the gate -------------------------------------------------------------
# gate_and_launch runs the FULL gate and launches the wrapped process only if
# every layer passes. It never launches on a failure. Sets CAP and GATE_LAYER
# (completeness | signature | ok | runtime). Reads NONO_EXTRA for extra nono args.
GATE_LAYER=""
gate_and_launch() {   # args: the wrapped command
  GATE_LAYER=""
  # The whole launch, shown up front so the audience sees what is being attempted:
  # stage 1 (our completeness check) && stage 2 (nono: signatures, sandbox, process).
  local -a cmd=( nono run --allow-cwd )
  [ "${#NONO_EXTRA[@]}" -gt 0 ] && cmd+=( "${NONO_EXTRA[@]}" )
  cmd+=( -- "$@" )
  echo "${BOLD}${YEL}>> Launch:${RESET} ${BOLD}python3 verify_artifact.py && ${cmd[*]}${RESET}"
  echo "${DIM}   (stage 2 runs only if stage 1 passes)${RESET}"
  # Layer 1: completeness, via the signed inventory. Stop on failure.
  local inv_out inv_rc l
  echo "${BOLD}${CYAN}\$ python3 verify_artifact.py${RESET}  ${DIM}(stage 1: completeness, the signed inventory)${RESET}"
  inv_out="$(python3 verify_artifact.py 2>&1)"; inv_rc=$?
  printf '%s\n' "$inv_out" | _tidy | _hl
  echo "${DIM}  [exit $inv_rc]${RESET}"
  if [ "$inv_rc" -ne 0 ]; then
    CAP="$inv_out"; GATE_LAYER="completeness"
    local -a why=()
    while IFS= read -r l; do why+=( "  $l" ); done < <(printf '%s\n' "$inv_out" \
      | grep -E '^ +[a-z]+: ' | sed -E 's/^ +//; s/: +/: /' | head -3)
    [ "${#why[@]}" -gt 0 ] || why=( "  $(printf '%s\n' "$inv_out" | head -1)" )
    refusal_box "stage 1, the completeness check (signed inventory)" "${cmd[*]}" "${why[@]}"
    return 20
  fi
  # Layers 2 and 3: per-file signatures + sandbox, via nono.
  echo "${BOLD}${CYAN}\$ ${cmd[*]}${RESET}  ${DIM}(stage 2: signatures, then the sandbox, then launch)${RESET}"
  CAP="$("${cmd[@]}" 2>&1)"; local nono_rc=$?
  printf '%s\n' "$CAP" | _footer_filter | _tidy | _hl
  echo "${DIM}  [exit $nono_rc]${RESET}"
  if printf '%s' "$CAP" | grep -q "failed trust verification"; then
    GATE_LAYER="signature"
    local -a why=()
    while IFS= read -r l; do why+=( "  $l" ); done < <(printf '%s\n' "$CAP" \
      | grep -E '^ *FAIL ' | sed -E 's/^ *FAIL //; s#file://[^ )]*/##g; s/ \(keyed\)//' | head -3)
    refusal_box "stage 2, nono's signature check" \
      "$* (nono stopped before launching it)" ${why[@]+"${why[@]}"}
  elif [ "$nono_rc" -eq 0 ]; then
    GATE_LAYER="ok"
  else
    GATE_LAYER="runtime"
  fi
  return "$nono_rc"
}

# Rebuild the inventory from the current file set and re-sign it with the trusted
# key, so the artifact is "approved" per its inventory. cwd must be WORK_DIR.
approve_inventory() {
  python3 "$DEMO_DIR/tools/build-inventory.py" >/dev/null || return 1
  nono -s trust sign "$INVENTORY_FILE" --keyref "$TRUSTED_REF" >/dev/null 2>&1 || return 1
}

# Fill INCLUDES from artifact-spec.json. cwd must be WORK_DIR.
compute_includes() {
  INCLUDES=()
  local pat
  while IFS= read -r pat; do
    [ -n "$pat" ] && INCLUDES+=(--include "$pat")
  done < <(python3 "$DEMO_DIR/tools/spec_includes.py")
}

# ---- assertions -----------------------------------------------------------
# The demo checks its own outcomes. Those checks are for the presenter, so they
# print small and dim under the verdict box: "as expected" when the outcome held
# (a refusal in a negative test is the expected outcome), and a loud yellow
# NOT AS EXPECTED when it did not. Red is kept for refusals and denials.
pass_msg() { echo "${GREEN}  ✔${RESET} ${DIM}as expected: $*${RESET}"; }
fail_msg() { echo "${BOLD}${YEL}  ✘ NOT AS EXPECTED:${RESET} $*"; DEMO_CHECK_FAILURES=$((${DEMO_CHECK_FAILURES:-0}+1)); LOCAL_FAILS=$((${LOCAL_FAILS:-0}+1)); }

# A clean run THROUGH THE GATE: exit 0, GATE_LAYER ok, and the run marker present.
assert_gate_ran() {   # <rc> <msg>
  if [ "$1" -eq 0 ] && [ "$GATE_LAYER" = "ok" ] && printf '%s' "$CAP" | grep -q "$DEMO_RUN_MARKER"; then
    pass_msg "$2 (gate ok, exit 0, run marker present)"
  else
    fail_msg "$2 (expected gate ok + exit 0 + run marker; got layer=$GATE_LAYER exit $1)"
  fi
}

# A real agent (AGENT=cc) that will not print our marker: gate ok + exit 0.
assert_gate_launched() {  # <rc> <msg>
  if [ "$1" -eq 0 ] && [ "$GATE_LAYER" = "ok" ]; then
    pass_msg "$2 (gate ok, exit 0)"
  else
    fail_msg "$2 (expected gate ok + exit 0; got layer=$GATE_LAYER exit $1)"
  fi
}

# A refusal BY THE GATE at a specific layer, with the wrapped process never run.
assert_gate_refused() {  # <rc> <expected-layer> <msg>
  if [ "$1" -ne 0 ] && [ "$GATE_LAYER" = "$2" ] && ! printf '%s' "$CAP" | grep -q "$DEMO_RUN_MARKER"; then
    pass_msg "$3 (at the $2 layer; no run marker)"
  else
    fail_msg "$3 (expected refusal at the $2 layer with no run marker; got layer=$GATE_LAYER exit $1)"
  fi
}

# Assert a specific cause string (e.g. unsigned vs untrusted) in the gate output.
assert_cause() { # <regex> <msg>
  if printf '%s' "$CAP" | grep -qiE "$1"; then echo "${GREEN}  ✔${RESET} ${DIM}reason: $2${RESET}"
  else fail_msg "$2 (expected /$1/ in the output)"; fi
}

# A setup/signing command that MUST succeed.
require_ok() { # <rc> <msg>
  if [ "$1" -eq 0 ]; then return 0; else fail_msg "$2 (command failed, exit $1)"; return 1; fi
}

# End a beat: nonzero if any of this command's own checks failed.
end_cmd() { [ "${LOCAL_FAILS:-0}" -eq 0 ]; }

need_nono() { command -v nono >/dev/null 2>&1 || { echo "${RED}nono is not on PATH.${RESET} brew install nono  (or cargo install nono-cli)"; exit 1; }; }
