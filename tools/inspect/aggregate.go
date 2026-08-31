// Layer aggregation: read one build directory's verification evidence into a JSON shape
// the dashboard renders. Read-only; every layer answers "무엇으로 검증되었나" first.
package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

// same heuristic as core/build/harden.py::_INHERENT_RE — outputs that differ per run by nature.
var inherentRe = regexp.MustCompile(`\b\d{2}:\d{2}\b|\btotal \d+\b|Aug|Jan|Feb|Mar|Apr|May|Jun|Jul|Sep|Oct|Nov|Dec`)

type M = map[string]any

func readJSON(path string) M {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var out M
	if json.Unmarshal(data, &out) != nil {
		return nil
	}
	return out
}

func readYAML(path string) M {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var out M
	if yaml.Unmarshal(data, &out) != nil {
		return nil
	}
	return out
}

func asList(v any) []any {
	if l, ok := v.([]any); ok {
		return l
	}
	return nil
}

func asMap(v any) M {
	if m, ok := v.(M); ok {
		return m
	}
	return nil
}

func num(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int:
		return float64(n)
	}
	return 0
}

func str(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

// traceSteps unwraps build trace.json ({"traces": [...]} or a bare TraceIR).
func traceSteps(root string) ([]any, M) {
	payload := readJSON(filepath.Join(root, "trace.json"))
	if payload == nil {
		return nil, nil
	}
	tr := payload
	if traces := asList(payload["traces"]); len(traces) > 0 {
		tr = asMap(traces[0])
	}
	return asList(tr["steps"]), tr
}

func layerCapture(root string) M {
	steps, tr := traceSteps(root)
	if steps == nil {
		return M{"present": false}
	}
	rows := []M{}
	var tokens, cached float64
	for _, s := range steps {
		sm := asMap(s)
		usage := asMap(sm["token_usage"])
		out := asMap(sm["output"])
		t := num(usage["total_tokens"])
		c := num(sm["cached_tokens"])
		tokens += t
		cached += c
		rows = append(rows, M{
			"step": str(sm["step_id"]), "action": str(sm["action"]), "model": str(sm["model"]),
			"tokens": t, "cached": c, "latency_ms": num(sm["latency_ms"]),
			"tool_calls": len(asList(out["tool_calls"])),
			"has_result": out != nil && out["tool_result"] != nil,
		})
	}
	prov := asMap(tr["provenance"])
	return M{"present": true, "run_id": str(tr["run_id"]), "source_agent": str(tr["source_agent"]),
		"agent_version": str(prov["agent_version"]), "protocol": str(asMap(prov["metadata"])["protocol"]),
		"steps": rows, "tokens": tokens, "cached": cached}
}

func layerCompile(root string) M {
	work := readYAML(filepath.Join(root, "work.yaml"))
	if work == nil {
		return M{"present": false}
	}
	execs := asMap(work["executors"])
	actions := []M{}
	tiers := map[string]int{}
	for _, a := range asList(work["actions"]) {
		name := str(a)
		tier := "frontier_llm"
		if e := asMap(execs[name]); e != nil {
			tier = str(e["type"])
		}
		tiers[tier]++
		actions = append(actions, M{"action": name, "tier": tier})
	}
	params := readJSON(filepath.Join(root, "PARAMS.json"))
	return M{"present": true, "work": str(work["work"]), "actions": actions, "tiers": tiers,
		"invariants": asList(work["invariants"]), "params": params["params"],
		"synthesized": params["synthesized_actions"], "escalation": work["escalation"]}
}

func layerBench(root string) M {
	bench := readJSON(filepath.Join(root, "benchmark.json"))
	if bench == nil {
		return M{"present": false}
	}
	steps := []M{}
	for _, a := range asList(bench["actions"]) {
		am := asMap(a)
		for _, s := range asList(am["steps"]) {
			sm := asMap(s)
			match, hasMatch := sm["output_match"].(bool)
			status := "not-compared"
			if hasMatch {
				if match {
					status = "match"
				} else if inherentRe.MatchString(str(sm["recorded_output"])) && inherentRe.MatchString(str(sm["compiled_output"])) {
					status = "inherent"
				} else {
					status = "mismatch"
				}
			}
			steps = append(steps, M{
				"step": str(sm["step_id"]), "action": str(am["action"]), "tier": str(am["tier"]),
				"executor": str(sm["executor_used"]), "status": status, "note": str(sm["note"]),
				"recorded_tokens": num(sm["recorded_tokens"]), "compiled_tokens": num(sm["compiled_tokens"]),
				"recorded_latency_ms": num(sm["recorded_latency_ms"]), "compiled_latency_ms": num(sm["compiled_latency_ms"]),
			})
		}
	}
	return M{"present": true, "totals": bench["totals"], "by_model": bench["by_model"], "steps": steps}
}

func layerSLM(root string) M {
	dirs, _ := filepath.Glob(filepath.Join(root, "models", "slm", "*"))
	actions := []M{}
	for _, dir := range dirs {
		action := filepath.Base(dir)
		entry := M{"action": action}
		if rt := readJSON(filepath.Join(dir, "runtime.json")); rt != nil {
			entry["promoted"] = true
			entry["model"] = str(rt["model"])
		} else {
			entry["promoted"] = false
		}
		if ev := readJSON(filepath.Join(dir, "promotion_eval.json")); ev != nil {
			entry["totals"] = ev["totals"]
			evals := []M{}
			for _, e := range asList(ev["evaluations"]) {
				em := asMap(e)
				evals = append(evals, M{"step": str(em["step_id"]), "gate": str(em["gate"]),
					"checks": em["checks"], "tokens": num(em["tokens"]), "score": num(em["score"])})
			}
			entry["evaluations"] = evals
		}
		if data, err := os.ReadFile(filepath.Join(dir, "fleet_evals.json")); err == nil {
			var hist []M
			if json.Unmarshal(data, &hist) == nil {
				rows := []any{}
				for _, h := range hist {
					rows = append(rows, h["totals"])
				}
				entry["fleet"] = rows
			}
		}
		actions = append(actions, entry)
	}
	return M{"present": len(actions) > 0, "actions": actions}
}

func layerCache(root string) M {
	files, _ := filepath.Glob(filepath.Join(root, "cache", "*", "*.json"))
	entries := []M{}
	for _, f := range files {
		e := readJSON(f)
		if e == nil {
			continue
		}
		sha := str(e["upstream_sha"])
		if len(sha) > 8 {
			sha = sha[:8]
		}
		var fileCount int
		if fm := asMap(e["files"]); fm != nil {
			fileCount = len(fm)
		}
		entries = append(entries, M{"action": str(e["action"]), "params": e["params"],
			"source": str(e["source"]), "at": str(e["at"]), "upstream_sha": sha, "files": fileCount,
			"fingerprinted": sha != ""})
	}
	sort.Slice(entries, func(i, j int) bool { return str(entries[i]["at"]) > str(entries[j]["at"]) })
	return M{"present": len(entries) > 0, "entries": entries}
}

func layerHarden(root string) M {
	h := readJSON(filepath.Join(root, "harden.json"))
	if h == nil {
		return M{"present": false}
	}
	return M{"present": true, "converged": h["converged"], "final": h["final"],
		"stopped_because": h["stopped_because"], "needs_human": h["needs_human"],
		"inherent": h["inherent"], "iterations": h["iterations"], "tokens_total": h["tokens_total"],
		"attempts": h["attempts"]}
}

func layerLedger(root string) M {
	data, err := os.ReadFile(filepath.Join(root, "ledger.jsonl"))
	if err != nil {
		return M{"present": false}
	}
	rows := []M{}
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		var row M
		if json.Unmarshal([]byte(line), &row) == nil {
			rows = append(rows, row)
		}
	}
	if len(rows) > 200 {
		rows = rows[len(rows)-200:]
	}
	return M{"present": len(rows) > 0, "rows": rows}
}

func layerPromotionDocs(root string) M {
	// PROMOTION.md / HARDEN.md / TRAINING.md raw text for the evidence drawer
	docs := M{}
	for _, name := range []string{"HARDEN.md", "BENCHMARK.md"} {
		if data, err := os.ReadFile(filepath.Join(root, name)); err == nil {
			docs[name] = string(data)
		}
	}
	matches, _ := filepath.Glob(filepath.Join(root, "models", "slm", "*", "PROMOTION.md"))
	for _, m := range matches {
		if data, err := os.ReadFile(m); err == nil {
			docs[filepath.Base(filepath.Dir(m))+"/PROMOTION.md"] = string(data)
		}
	}
	return docs
}

// Aggregate builds the full per-build payload.
func Aggregate(root string) M {
	return M{
		"name":    filepath.Base(root),
		"capture": layerCapture(root),
		"compile": layerCompile(root),
		"bench":   layerBench(root),
		"slm":     layerSLM(root),
		"cache":   layerCache(root),
		"harden":  layerHarden(root),
		"ledger":  layerLedger(root),
		"docs":    layerPromotionDocs(root),
	}
}

// ListBuilds scans the base dir for build directories (work.yaml present) with a one-line summary.
func ListBuilds(base string) []M {
	entries, _ := os.ReadDir(base)
	out := []M{}
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		root := filepath.Join(base, e.Name())
		work := readYAML(filepath.Join(root, "work.yaml"))
		if work == nil {
			continue
		}
		row := M{"name": e.Name(), "work": str(work["work"]), "actions": len(asList(work["actions"]))}
		if bench := readJSON(filepath.Join(root, "benchmark.json")); bench != nil {
			row["bench"] = bench["totals"]
		}
		row["has_trace"] = fileExists(filepath.Join(root, "trace.json"))
		row["has_harden"] = fileExists(filepath.Join(root, "harden.json"))
		row["cache_entries"] = countGlob(filepath.Join(root, "cache", "*", "*.json"))
		row["slm_promoted"] = countGlob(filepath.Join(root, "models", "slm", "*", "runtime.json"))
		out = append(out, row)
	}
	sort.Slice(out, func(i, j int) bool { return str(out[i]["name"]) < str(out[j]["name"]) })
	return out
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func countGlob(pattern string) int {
	m, _ := filepath.Glob(pattern)
	return len(m)
}
