#!/usr/bin/env bash
# The real-host smoke AGENTS.md's merge gate names: one real session saves a memory,
# one loads it, on this device — plus the session.v1 Conformance items that only a
# real session can show (§2 announce, §3 save-in-turn with a §4 discriminating pair,
# §6 /remember, exit latency vs a control, §10 store unwritable).
#
# It runs `amplifier run` — a headless one-shot session — against a TEMP store.
# The steward's real store at ~/.amplifier/memory is never written to (PINS.md).
#
#   tests/smoke/real_session.sh            # run everything, write tests/smoke/evidence/
#
# Shape of the discriminating pair. session.v1's Conformance says the task-scoped
# instruction produces no save "in the same session" — so it is one session per
# turn here, which is also all a one-shot `amplifier run` can give:
#
#   session A  task-scoped only ......... §2 empty announce + §4 no save
#   session B  standing correction only .. §3 save in that turn, quote trailer
#   session C  a later session ........... §2 load announce, id cited
#   session D  /remember <text> .......... §6, writer: human
#
# Putting BOTH halves in ONE turn is a measured failure and not the shape used here:
# see tests/smoke/evidence/session-1.txt and session-1c-pair-repeat.txt — with
# "…always two-space indentation. Separately, for this task only, reply with exactly
# the word ok." the model obeys the literal reply constraint and skips the save,
# reproduced 2/2, while the correction alone saves 1/1 (session-1b-correction-alone.txt).
#
# Every check prints what it observed. A check that cannot be made here says so in
# the honesty form: "<item> — Can't check headless; what a human sees interactively is …"

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVIDENCE="$HERE/evidence"
mkdir -p "$EVIDENCE"

strip_ansi() { sed -r 's/\x1B\[[0-9;]*[mGKHJ]//g'; }

PASS=0
FAIL=0
note() { printf '\n=== %s ===\n' "$1"; }
verdict() { # verdict <PASS|FAIL-cause> <item>
  if [[ "$1" == PASS ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi
  printf '  -> %s: %s\n' "$2" "$1"
}
# session <evidence-file> <prompt> — the header line is written by this run, so an
# evidence file can never be mistaken for an older one (store path + timestamp).
session() {
  local out="$1" prompt="$2"
  { echo "# store=$AMPLIFIER_MEMORY_HOME  date=$(date -Iseconds)  host=$(hostname)"
    echo "# prompt: $prompt"; } > "$out"
  amplifier run "$prompt" 2>&1 | strip_ansi >> "$out"
  cat "$out"
}
# `grep -c` prints 0 AND exits 1 on no match, so an `|| echo 0` fallback would print
# "0" twice and every numeric comparison against it would be false. Capture, default, echo.
mem_lines() {
  local n
  n=$(grep -c '^- \[m-' "$AMPLIFIER_MEMORY_HOME/MEMORY.md" 2>/dev/null)
  echo "${n:-0}"
}

STORE="$(mktemp -d /tmp/amm-smoke-XXXXXX)"
export AMPLIFIER_MEMORY_HOME="$STORE"
note "temp store (the real store at ~/.amplifier/memory is never touched)"
echo "AMPLIFIER_MEMORY_HOME=$STORE"
amplifier-memory init

# ------------------------------------------- session A0: §2 empty-store announce
# A neutral prompt, deliberately. The announce is a model instruction inside the
# injected block, so a human instruction that constrains the reply can outrank it —
# measured: "reply with exactly the word ok" suppressed the announce in 1 of 2 runs
# (see the note under session A). Asserting §2 through such a prompt would be
# testing the prompt, not the contract.
note "session A0 — an empty store announces itself on a neutral prompt (§2)"
A0="$EVIDENCE/session-A0-empty-announce.txt"
session "$A0" "In one line: what is 2 + 2?"
okA0=PASS
grep -q "No memories yet" "$A0" || { echo "MISSING: 'No memories yet' (session.v1 §2 empty-store announce)"; okA0="FAIL-no-empty-announce"; }
echo "--- '- [m-' lines: $(mem_lines) (still 0 — nothing standing was said) ---"
[[ "$(mem_lines)" == "0" ]] || okA0="FAIL-saved-something-from-a-neutral-prompt"
verdict "$okA0" "item 4a (§2 empty-store announce)"

# ------------------------------------------- session A: §4 no save on task-scoped
note "session A — a task-scoped instruction saves nothing (§4, the discriminating half)"
A="$EVIDENCE/session-A-task-scoped.txt"
session "$A" "For this task only, reply with exactly the word ok."
okA=PASS
echo "--- '- [m-' lines after a task-scoped instruction: $(mem_lines) (must be 0 — session.v1 §4) ---"
[[ "$(mem_lines)" == "0" ]] || okA="FAIL-task-scoped-instruction-was-saved"
if grep -q "No memories yet" "$A"; then
  echo "note: the §2 announce survived the literal-reply instruction in this run"
else
  echo "note: the §2 announce did NOT survive 'reply with exactly the word ok' in this run —"
  echo "      a human instruction constraining the reply can outrank the announce"
  echo "      instruction in the injected block. §2 is asserted by session A0 instead."
fi
verdict "$okA" "item 4a-pair (§4: the task-scoped half saves nothing)"

# ------------------------------------------- session B: §3 save in the same turn
note "session B — a standing correction: saved in that turn, with the verbatim quote"
B="$EVIDENCE/session-B-correction.txt"
session "$B" "For future reference: never use tabs in YAML files you write for me; always two-space indentation."
okB=PASS
grep -q 'Saved memory m-001' "$B" || { echo "MISSING: 'Saved memory m-001' (session.v1 §3)"; okB="FAIL-no-save-announced"; }
echo "--- MEMORY.md ---"; cat "$STORE/MEMORY.md"
echo "--- '- [m-' lines: $(mem_lines) (must be exactly 1) ---"
[[ "$(mem_lines)" == "1" ]] || okB="FAIL-line-count-$(mem_lines)"
grep -qi 'tab\|yaml' "$STORE/MEMORY.md" || okB="FAIL-saved-line-not-about-tabs-or-yaml"
echo "--- git log -1 --format=%B ---"; git -C "$STORE" log -1 --format=%B
git -C "$STORE" log -1 --format=%B | grep -q '^quote:' || { echo "MISSING: a 'quote:' trailer"; okB="FAIL-no-quote-trailer"; }
git -C "$STORE" log -1 --format=%B | grep -qi 'tabs in YAML' || { echo "MISSING: the human's own words in the quote"; okB="FAIL-quote-not-the-humans-words"; }
# Where the §3 announce actually landed. Both places satisfy "announced in the
# transcript" (§8), but they are not the same thing and the difference is recorded
# rather than smoothed over: measured here, the sentence arrives as the memory tool's
# own result line, while the assistant's closing line is the §2 load announce.
if tail -6 "$B" | grep -q 'Saved memory m-001'; then
  echo "note: the §3 announce is the assistant's own closing line"
else
  echo "note: the §3 announce reached the transcript as the memory tool's result line;"
  echo "      the assistant's closing line was the §2 load announce, not the save sentence"
fi
verdict "$okB" "item 4b (§3 save in the turn the correction was stated)"

# ------------------------------------------- session C: §2 load announce
note "session C — a later session must announce the memory it loaded"
C="$EVIDENCE/session-C-load.txt"
session "$C" "In one line: what standing preferences of mine do you have loaded, and cite the memory id."
okC=PASS
grep -q "Loaded 1 memories" "$C" || { echo "MISSING: 'Loaded 1 memories'"; okC="FAIL-no-load-announce"; }
grep -q "m-001" "$C"             || { echo "MISSING: 'm-001'"; okC="FAIL-id-not-cited"; }
verdict "$okC" "item 5 (load announced in a later session, id cited)"

# ------------------------------------------- session D: §6 /remember
note "session D — /remember from a shell session"
D="$EVIDENCE/session-D-remember.txt"
session "$D" "/remember always run make check before pushing"
okD=PASS
grep -q "Saved memory m-002" "$D" || okD="FAIL-no-m-002-saved"
echo "--- MEMORY.md ---"; cat "$STORE/MEMORY.md"
echo "--- git log -1 --format=%B ---"; git -C "$STORE" log -1 --format=%B
git -C "$STORE" log -1 --format=%B | grep -q 'writer: human' || {
  [[ "$okD" == PASS ]] && okD="FAIL-writer-not-human"; }
echo "/remember — Can't check headless; what a human sees interactively is the CLI's"
echo "SKILL_SHORTCUTS registry intercepting the typed line and returning a load_skill"
echo "action (modules/tool-memory/README.md). In a one-shot \`amplifier run\` the line is"
echo "an ordinary prompt: the model reads it, loads the remember skill itself, and the"
echo "save that follows is the same library call with writer=human — printed above."
verdict "$okD" "item 6 (/remember reaches the writer with writer: human)"

# ------------------------------------------- item 7: exit latency
note "exit latency — 3 runs with the store, 3 control runs with no store"
LAT="$EVIDENCE/latency.txt"
{
  echo "# store=$STORE  date=$(date -Iseconds)"
  echo '# 1-turn proxy for session.v1 Conformance 2-turn wording: `amplifier run` is a'
  echo '# one-shot headless session, so a 2-turn session is not available from a shell.'
  echo '# Control = AMPLIFIER_MEMORY_HOME=/nonexistent: the hook fails open and injects'
  echo '# nothing (session.v1 §10). `amplifier run --help` offers no way to exclude an app'
  echo "# bundle, so this is the closest available 'without the bundle'."
} > "$LAT"
timeit() { # timeit <label> <store-home>
  local label="$1" home="$2" t0 t1
  t0=$(date +%s.%N)
  env AMPLIFIER_MEMORY_HOME="$home" amplifier run "reply ok" >/dev/null 2>/dev/null
  t1=$(date +%s.%N)
  awk -v a="$t0" -v b="$t1" -v l="$label" 'BEGIN{printf "%s %.2f\n", l, b-a}'
}
for i in 1 2 3; do timeit "with-store-$i" "$STORE" | tee -a "$LAT"; done
for i in 1 2 3; do timeit "control-$i" "/nonexistent" | tee -a "$LAT"; done
median() { grep "^$1" "$LAT" | awk '{print $2}' | sort -n | sed -n 2p; }
MW=$(median with-store); MC=$(median control)
DIFF=$(awk -v a="$MW" -v b="$MC" 'BEGIN{d=a-b; if(d<0)d=-d; printf "%.2f", d}')
echo "median with-store=${MW}s  median control=${MC}s  |diff|=${DIFF}s (must be < 2s)" | tee -a "$LAT"
ok7=PASS
awk -v d="$DIFF" 'BEGIN{exit !(d < 2)}' || ok7="FAIL-latency-diff-${DIFF}s"
verdict "$ok7" "item 7 (exit latency within noise)"

# ------------------------------------------- item 8: store unwritable
note "store unwritable — the session must complete, fail open, and log one line"
ERRLOG="$HOME/.amplifier/memory-errors.log"
before=$( [[ -f "$ERRLOG" ]] && wc -l < "$ERRLOG" || echo 0 )
chmod 000 "$STORE"
U="$EVIDENCE/session-E-unwritable.txt"
session "$U" "reply ok"
chmod 755 "$STORE"
after=$( [[ -f "$ERRLOG" ]] && wc -l < "$ERRLOG" || echo 0 )
echo "--- $ERRLOG: $before -> $after line(s) ---"
echo "--- tail -1 ---"; [[ -f "$ERRLOG" ]] && tail -1 "$ERRLOG" || echo "(no error log)"
ok8=PASS
grep -qi 'Traceback' "$U" && ok8="FAIL-traceback-in-session-output"
[[ "$after" -gt "$before" ]] || ok8="FAIL-no-line-appended-to-memory-errors.log"
verdict "$ok8" "item 8 (store unwritable: fail open, one logged line)"

# -------------------------------------------
note "secret scan (no key-shaped string may be committed as evidence)"
if grep -nEi 'sk-[A-Za-z0-9]{8}|api[_-]?key["'\'':= ]+[A-Za-z0-9_-]{12}|bearer [A-Za-z0-9._-]{12}' "$EVIDENCE"/*.txt; then
  echo "!! redact the lines above before committing"
else
  echo "clean: no key-shaped strings in tests/smoke/evidence/"
fi

note "summary"
echo "store kept for inspection: $STORE"
echo "PASS=$PASS FAIL=$FAIL"
exit $(( FAIL > 0 ))
