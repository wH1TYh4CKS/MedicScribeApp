#!/usr/bin/env bash
# Send a task to a locally-served model and do something useful with the answer.
#
# Talks straight to an OpenAI-compatible endpoint (vLLM or llama.cpp), so it does
# NOT swap the served model the way `llmw-edit` does — safe to run while that
# model is also serving something else.
#
#   ./scripts/llm_task.sh review --range HEAD~3..HEAD
#   ./scripts/llm_task.sh review --file server/.../app.js
#   ./scripts/llm_task.sh edit --file path/to.css --task "raise .foo contrast to 4.5:1"
#   ./scripts/llm_task.sh ask  --task "why would vLLM report 0 KV blocks?"
#
# `edit` never writes in place: it writes <file>.llmnew and prints a diff. Apply
# with --apply once the diff looks right.
#
# Env: ENDPOINT (default http://localhost:8000/v1), MODEL (default = first model
# the endpoint advertises), API_KEY, MAX_TOKENS, TEMP.
set -uo pipefail

ENDPOINT="${ENDPOINT:-http://localhost:8000/v1}"
API_KEY="${API_KEY:-}"
MAX_TOKENS="${MAX_TOKENS:-4096}"
TEMP="${TEMP:-0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MODE="${1:-}"; shift || true
FILE=""; TASK=""; RANGE=""; APPLY=0

while [ $# -gt 0 ]; do
    case "$1" in
        --file)  FILE="$2";  shift 2 ;;
        --task)  TASK="$2";  shift 2 ;;
        --range) RANGE="$2"; shift 2 ;;
        --apply) APPLY=1;    shift ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

die() { echo "$1" >&2; exit 1; }

resolve_model() {
    [ -n "${MODEL:-}" ] && { echo "$MODEL"; return; }
    curl -s -m 15 "$ENDPOINT/models" ${API_KEY:+-H "Authorization: Bearer $API_KEY"} \
        | python3 -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'])" 2>/dev/null
}

# One call. Reads system prompt + user prompt from files so no quoting games.
call_model() {  # $1=system-file $2=user-file
    python3 - "$ENDPOINT" "$(resolve_model)" "$1" "$2" "$MAX_TOKENS" "$TEMP" "$API_KEY" <<'PY'
import json, sys, urllib.request
endpoint, model, sysf, userf, maxtok, temp, key = sys.argv[1:8]
body = {
    "model": model,
    "messages": [
        {"role": "system", "content": open(sysf).read()},
        {"role": "user", "content": open(userf).read()},
    ],
    "max_tokens": int(maxtok),
    "temperature": float(temp),
    # Greedy decoding with no penalty degenerates on long inputs: a review of a
    # 500-line file looped one finding until the token budget ran out. Same fix
    # the note path uses (see llm/models/note_llm.yaml).
    "repetition_penalty": 1.05,
    # Thinking models otherwise bury the answer in a reasoning block.
    "chat_template_kwargs": {"enable_thinking": False},
}
headers = {"Content-Type": "application/json"}
if key:
    headers["Authorization"] = f"Bearer {key}"
req = urllib.request.Request(endpoint + "/chat/completions",
                             data=json.dumps(body).encode(), headers=headers)
try:
    d = json.loads(urllib.request.urlopen(req, timeout=600).read().decode())
except Exception as e:
    print(f"MODEL CALL FAILED: {e}", file=sys.stderr); sys.exit(1)
msg = d["choices"][0]["message"]
sys.stderr.write(f"[{model} · {d['usage']['completion_tokens']} tok out]\n")
print(msg.get("content") or "")
PY
}

# Strip a ```lang fence if the model wrapped the file in one.
unfence() {
    python3 -c "
import re, sys
s = sys.stdin.read().strip()
m = re.match(r'^\`\`\`[a-zA-Z]*\n(.*)\n\`\`\`$', s, re.S)
sys.stdout.write(m.group(1) if m else s)
"
}

mode_review() {
    local sysf userf content
    sysf=$(mktemp); userf=$(mktemp)
    cat > "$sysf" <<'EOF'
You are a senior code reviewer. Report only defects that would change behaviour,
break a user flow, or mislead a reader. No style opinions, no praise, no summary
of what the code does.

Format each finding on one line:
  <file>:<line>: <severity: BUG|RISK|NIT> <what is wrong>. <the fix>.

If you find nothing that meets that bar, reply exactly: NO FINDINGS.
EOF
    if [ -n "$FILE" ]; then
        [ -f "$ROOT/$FILE" ] || [ -f "$FILE" ] || die "no such file: $FILE"
        { echo "Review this file: $FILE"; echo; cat "${ROOT}/${FILE}" 2>/dev/null || cat "$FILE"; } > "$userf"
        call_model "$sysf" "$userf"
        rm -f "$sysf" "$userf"
        return
    fi

    # Diff review, one file per call. A whole feature branch's diff overruns the
    # served context window (the model 400s with no useful message), and one
    # oversized request would lose the entire review — per-file keeps each call
    # in budget and means one big file can't take the others down with it.
    local files
    files=$(cd "$ROOT" && git diff --name-only ${RANGE:+"$RANGE"})
    [ -z "$files" ] && die "nothing to review; working tree clean (or empty range)"

    local f content
    while read -r f; do
        [ -z "$f" ] && continue
        content=$(cd "$ROOT" && git diff ${RANGE:+"$RANGE"} -- "$f")
        [ -z "$content" ] && continue
        # ~4 chars/token, and the reply needs room too.
        if [ "${#content}" -gt 40000 ]; then
            echo "### $f — SKIPPED (diff too large for context: ${#content} chars)"
            continue
        fi
        echo "### $f"
        { echo "Review this diff."; echo; echo '```diff'; echo "$content"; echo '```'; } > "$userf"
        call_model "$sysf" "$userf"
        echo
    done <<< "$files"
    rm -f "$sysf" "$userf"
}

mode_edit() {
    [ -n "$FILE" ] || die "edit needs --file"
    [ -n "$TASK" ] || die "edit needs --task"
    local path="$ROOT/$FILE"; [ -f "$path" ] || path="$FILE"
    [ -f "$path" ] || die "no such file: $FILE"

    local sysf userf out
    sysf=$(mktemp); userf=$(mktemp); out="${path}.llmnew"
    cat > "$sysf" <<'EOF'
You edit source files. Output the COMPLETE modified file and nothing else: no
prose, no explanation, no markdown fence, no diff.

Rules:
- Change only what the task requires. Preserve every other line byte-for-byte.
- Match the file's existing style, indentation, and comment voice.
- Never invent APIs, imports, or config keys that are not already present.
- If the task cannot be done safely, output the file completely unchanged.
EOF
    { echo "TASK: $TASK"; echo; echo "FILE: $FILE"; echo; cat "$path"; } > "$userf"
    # Land the reply in a staging file and check the call actually succeeded before
    # unfencing. Piping straight into $out would leave a truncated file looking like
    # a valid candidate if the model died mid-stream — and --apply would ship it.
    local raw; raw=$(mktemp)
    if ! call_model "$sysf" "$userf" > "$raw"; then
        rm -f "$sysf" "$userf" "$raw"; die "model call failed; file untouched"
    fi
    unfence < "$raw" > "$out"
    rm -f "$raw"

    if [ ! -s "$out" ]; then
        rm -f "$sysf" "$userf" "$out"; die "model returned nothing; file untouched"
    fi
    echo "--- proposed diff ---"
    diff -u "$path" "$out"
    if [ "$APPLY" = "1" ]; then
        cp "$path" "${path}.bak" && mv "$out" "$path"
        echo "APPLIED (backup at ${path}.bak)"
    else
        echo "not applied. review, then re-run with --apply (candidate kept at $out)"
    fi
    rm -f "$sysf" "$userf"
}

mode_ask() {
    [ -n "$TASK" ] || die "ask needs --task"
    local sysf userf
    sysf=$(mktemp); userf=$(mktemp)
    echo "Answer concisely and concretely. Say plainly when you do not know." > "$sysf"
    { echo "$TASK"; [ -n "$FILE" ] && { echo; cat "${ROOT}/${FILE}" 2>/dev/null || cat "$FILE"; }; } > "$userf"
    call_model "$sysf" "$userf"
    rm -f "$sysf" "$userf"
}

case "$MODE" in
    review) mode_review ;;
    edit)   mode_edit ;;
    ask)    mode_ask ;;
    *) sed -n '2,17p' "${BASH_SOURCE[0]}"; exit 2 ;;
esac
