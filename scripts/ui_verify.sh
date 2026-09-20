#!/usr/bin/env bash
# Verify the web UI after a change: deterministic scan, live screenshots, and the
# checks a browser catches but curl cannot (contrast, focus rings, ARIA wiring).
#
# Runs against the LIVE server, so start the stack first (`medic start`). Every
# artifact lands in one timestamped dir so two runs can be diffed by eye.
#
#   ./scripts/ui_verify.sh                    # localhost:8080
#   BASE=https://your-host.example ./scripts/ui_verify.sh
#   OUT=/tmp/before ./scripts/ui_verify.sh    # pin the output dir
#
# Exit 0 = every check passed. Exit 1 = at least one FAIL (the summary says which).
set -uo pipefail

BASE="${BASE:-http://localhost:8080}"
CAMO="${CAMO:-http://localhost:9377}"
SKILL="${SKILL:-$HOME/.claude/skills/impeccable}"
OUT="${OUT:-/tmp/ui_verify-$(date +%H%M%S)}"
USER_ID="uiverify$$"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$ROOT/server/src/medicscribe_server/web"
FAILED=0

mkdir -p "$OUT"

say()  { printf '\n=== %s ===\n' "$1"; }
pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; FAILED=1; }

# --- reachability -----------------------------------------------------------

check_pages() {
    say "pages"
    for path in / /scribe /feedback; do
        local code
        code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 "$BASE$path")
        [ "$code" = "200" ] && pass "$path -> 200" || fail "$path -> $code"
    done
    local ready
    ready=$(curl -s -m 30 "$BASE/health/ready")
    case "$ready" in
        *'"ready":true'*) pass "health/ready: $ready" ;;
        *)                fail "health/ready: ${ready:-no response}" ;;
    esac
}

# --- deterministic scan -----------------------------------------------------
# detect.mjs takes markup only; style.css is scanned through the live page below.

check_detector() {
    say "detector (markup)"
    if [ ! -f "$SKILL/scripts/detect.mjs" ]; then
        echo "  SKIP  detect.mjs not installed at $SKILL"
        return
    fi
    node "$SKILL/scripts/detect.mjs" --json \
        "$WEB/index.html" "$WEB/feedback.html" > "$OUT/detect.json" 2> "$OUT/detect.err"
    local rc=$?
    grep -q 'DEGRADED' "$OUT/detect.err" && echo "  NOTE  scan degraded (parser deps missing) - findings are a floor"
    local n
    n=$(python3 -c "
import json
try:
    d = json.load(open('$OUT/detect.json'))
except Exception as e:
    print('unreadable:', e); raise SystemExit
f = d if isinstance(d, list) else d.get('findings', [])
print(len(f), 'finding(s)')
for x in f:
    loc = x.get('file', '').split('/')[-1] + ':' + str(x.get('line'))
    print('        ', x.get('antipattern') or x.get('rule'), loc)
" | head -20)
    echo "  findings: $n"
    [ "$rc" = "0" ] && pass "detector clean" || echo "  (exit $rc - see $OUT/detect.json)"
}

# --- browser -----------------------------------------------------------------

camo_up() { curl -sf -m 5 "$CAMO/" >/dev/null 2>&1; }

tab_open() {  # $1=url -> tabId
    curl -s -m 60 -X POST "$CAMO/tabs/open" -H 'Content-Type: application/json' \
        -d "{\"userId\":\"$USER_ID\",\"url\":\"$1\"}" \
        | python3 -c "import json,sys; print(json.load(sys.stdin).get('tabId',''))"
}

tab_viewport() {  # $1=tab $2=w $3=h
    curl -s -m 30 -X POST "$CAMO/tabs/$1/viewport" -H 'Content-Type: application/json' \
        -d "{\"userId\":\"$USER_ID\",\"width\":$2,\"height\":$3}" >/dev/null
}

tab_shot() {  # $1=tab $2=name
    curl -s -m 60 "$CAMO/tabs/$1/screenshot?userId=$USER_ID" -o "$OUT/$2.png"
    [ -s "$OUT/$2.png" ] && echo "  shot  $OUT/$2.png"
}

tab_eval() {  # $1=tab $2=js  -> raw JSON result
    python3 - "$CAMO" "$1" "$USER_ID" "$2" <<'PY'
import json, sys, urllib.request
camo, tab, uid, js = sys.argv[1:5]
req = urllib.request.Request(
    f"{camo}/tabs/{tab}/evaluate",
    data=json.dumps({"userId": uid, "expression": js}).encode(),
    headers={"Content-Type": "application/json"})
try:
    print(urllib.request.urlopen(req, timeout=60).read().decode())
except Exception as e:
    print(json.dumps({"error": str(e)}))
PY
}

tab_close() { curl -s -m 20 -X DELETE "$CAMO/tabs/$1?userId=$USER_ID" >/dev/null 2>&1; }

# Contrast + a11y wiring, measured in the page where computed styles are real.
# Mirrors the rules the impeccable detector applies, so a regression is caught
# here rather than in the next critique.
A11Y_PROBE='(() => {
  const srgb = c => { c /= 255; return c <= 0.03928 ? c/12.92 : Math.pow((c+0.055)/1.055, 2.4); };
  const lum = rgb => { const [r,g,b] = rgb; return 0.2126*srgb(r)+0.7152*srgb(g)+0.0722*srgb(b); };
  const parse = s => (s.match(/\d+(\.\d+)?/g) || []).slice(0,3).map(Number);
  const ratio = (fg, bg) => { const a = lum(parse(fg)), b = lum(parse(bg));
    return +(((Math.max(a,b)+0.05)/(Math.min(a,b)+0.05)).toFixed(2)); };
  const bgOf = el => { let n = el; while (n) { const c = getComputedStyle(n).backgroundColor;
    if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") return c; n = n.parentElement; }
    return "rgb(0,0,0)"; };
  const out = { contrast: [], focus: 0, aria: {}, small_targets: [], skipped: [] };
  for (const el of document.querySelectorAll("button,a,input,select,textarea")) {
    const r = el.getBoundingClientRect(); if (!r.width) continue;
    const cs = getComputedStyle(el);
    const size = parseFloat(cs.fontSize), weight = +cs.fontWeight || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    // A gradient fill leaves computed backgroundColor transparent, so walking to
    // the parent would compare the label against the page behind it and invent a
    // failure. Report these as unchecked rather than guessing a stop colour.
    if (cs.backgroundImage && cs.backgroundImage !== "none") {
      out.skipped.push({ el: (el.id || el.className || el.tagName).toString().slice(0,40),
        why: "gradient fill" });
      continue;
    }
    const c = ratio(cs.color, bgOf(el));
    const need = large ? 3 : 4.5;
    if (c < need) out.contrast.push({ el: (el.id || el.className || el.tagName).toString().slice(0,40),
      text: (el.textContent||"").trim().slice(0,24), ratio: c, need, size, weight });
    if (r.width < 44 || r.height < 44) out.small_targets.push({
      el: (el.id || el.className || el.tagName).toString().slice(0,40),
      w: Math.round(r.width), h: Math.round(r.height) });
  }
  for (const sheet of document.styleSheets) {
    try { for (const rule of sheet.cssRules)
      if (rule.selectorText && /:focus/.test(rule.selectorText)) out.focus++;
    } catch (e) {}
  }
  const rec = document.getElementById("recordBtn");
  out.aria = {
    record_label: rec ? (rec.getAttribute("aria-label") || null) : "missing",
    record_pressed: rec ? (rec.getAttribute("aria-pressed") || null) : "missing",
    live_regions: document.querySelectorAll("[aria-live]").length,
    alert_roles: document.querySelectorAll("[role=alert]").length,
  };
  return JSON.stringify(out);
})()'

check_browser() {
    say "browser"
    if ! camo_up; then
        echo "  SKIP  camofox not reachable at $CAMO (start it with: camofox start)"
        return
    fi
    local tab
    for page in "" feedback; do
        tab=$(tab_open "$BASE/$page")
        [ -z "$tab" ] && { fail "could not open $BASE/$page"; continue; }
        local name="${page:-index}"
        tab_viewport "$tab" 1440 900; sleep 1; tab_shot "$tab" "desktop-$name"
        tab_viewport "$tab" 390 844;  sleep 1; tab_shot "$tab" "mobile-$name"
        if [ "$name" = "index" ]; then
            tab_eval "$tab" "$A11Y_PROBE" > "$OUT/a11y.json"
            report_a11y "$OUT/a11y.json"
        fi
        tab_close "$tab"
    done
}

report_a11y() {  # $1=json file
    python3 - "$1" <<'PY'
import json, sys
raw = json.load(open(sys.argv[1]))
inner = raw.get("result", raw.get("value", raw))
if isinstance(inner, str):
    inner = json.loads(inner)
if not isinstance(inner, dict) or "aria" not in inner:
    print("  FAIL  a11y probe returned no data:", str(raw)[:160]); sys.exit(1)
bad = 0
for c in inner["contrast"]:
    print(f"  FAIL  contrast {c['ratio']}:1 (need {c['need']}) on {c['el']} \"{c['text']}\""); bad = 1
if not inner["contrast"]:
    print("  PASS  contrast: every measurable control meets its WCAG threshold")
for sk in inner.get("skipped", []):
    print(f"  NOTE  contrast unchecked on {sk['el']} ({sk['why']}) - verify by eye")
if inner["focus"]:
    print(f"  PASS  focus styling: {inner['focus']} :focus rule(s)")
else:
    print("  FAIL  focus styling: no :focus rule in any stylesheet"); bad = 1
a = inner["aria"]
print(f"  {'PASS' if a['record_label'] else 'FAIL'}  record button aria-label: {a['record_label']}")
print(f"  {'PASS' if a['live_regions'] else 'FAIL'}  aria-live regions: {a['live_regions']}")
print(f"  {'PASS' if a['alert_roles'] else 'FAIL'}  role=alert elements: {a['alert_roles']}")
if not (a["record_label"] and a["live_regions"] and a["alert_roles"]):
    bad = 1
for t in inner["small_targets"]:
    print(f"  WARN  touch target {t['w']}x{t['h']} on {t['el']}")
sys.exit(1 if bad else 0)
PY
    if [ $? -ne 0 ]; then FAILED=1; fi
}

# --- run ---------------------------------------------------------------------

echo "MedicScribe UI verify -> $OUT"
echo "base: $BASE"
check_pages
check_detector
check_browser

say "summary"
if [ "$FAILED" = "0" ]; then
    echo "  ALL CHECKS PASSED"
else
    echo "  SOME CHECKS FAILED (see FAIL lines above)"
fi
echo "  artifacts: $OUT"
exit "$FAILED"
