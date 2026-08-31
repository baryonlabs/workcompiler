package main

import (
	"os"
	"path/filepath"
	"testing"
)

func write(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestAggregateAndList(t *testing.T) {
	base := t.TempDir()
	root := filepath.Join(base, "demo")
	write(t, filepath.Join(root, "work.yaml"), "work: demo\nactions:\n  - shell_a\n  - respond\nexecutors:\n  shell_a: {type: code}\n  respond: {type: slm}\n")
	write(t, filepath.Join(root, "PARAMS.json"), `{"params":[{"name":"id","recorded_value":"X-1"}],"synthesized_actions":["shell_a"]}`)
	write(t, filepath.Join(root, "trace.json"), `{"traces":[{"run_id":"r1","source_agent":"codex-cli","result":{},"provenance":{"agent_version":"1.0","metadata":{"protocol":"responses"}},"steps":[{"step_id":"s1","action":"shell_a","model":"m","token_usage":{"total_tokens":100},"cached_tokens":40,"latency_ms":1000,"output":{"tool_calls":[{"id":"c"}],"tool_result":"ok"}}]}]}`)
	write(t, filepath.Join(root, "benchmark.json"), `{"totals":{"outputs_matched":1,"outputs_checked":2,"token_savings_pct":90.0},"actions":[{"action":"shell_a","tier":"code","steps":[{"step_id":"s1","executor_used":"code:x","output_match":true,"recorded_output":"a","compiled_output":"a","recorded_tokens":100,"compiled_tokens":0},{"step_id":"s2","executor_used":"code:x","output_match":false,"recorded_output":"Aug 29 12:33","compiled_output":"Aug 31 15:07","recorded_tokens":10,"compiled_tokens":0}]}]}`)
	write(t, filepath.Join(root, "cache", "shell_a", "k.json"), `{"action":"shell_a","params":{"id":"X-2"},"source":"claude","at":"2026-08-31T00:00:00","upstream_sha":"abcdef0123456789","files":{"f":"x"}}`)
	write(t, filepath.Join(root, "models", "slm", "respond", "runtime.json"), `{"model":"q3b"}`)
	write(t, filepath.Join(root, "harden.json"), `{"converged":true,"final":{"matched":2,"checked":2},"stopped_because":"done","iterations":[]}`)

	list := ListBuilds(base)
	if len(list) != 1 || list[0]["name"] != "demo" || list[0]["slm_promoted"].(int) != 1 {
		t.Fatalf("list = %#v", list)
	}
	agg := Aggregate(root)
	cap := agg["capture"].(M)
	if cap["present"] != true || cap["source_agent"] != "codex-cli" || cap["tokens"].(float64) != 100 {
		t.Fatalf("capture = %#v", cap)
	}
	bench := agg["bench"].(M)
	steps := bench["steps"].([]M)
	if steps[0]["status"] != "match" || steps[1]["status"] != "inherent" {
		t.Fatalf("bench statuses = %v, %v", steps[0]["status"], steps[1]["status"])
	}
	cacheL := agg["cache"].(M)
	entry := cacheL["entries"].([]M)[0]
	if entry["upstream_sha"] != "abcdef01" || entry["fingerprinted"] != true {
		t.Fatalf("cache = %#v", entry)
	}
	slm := agg["slm"].(M)
	if slm["actions"].([]M)[0]["promoted"] != true {
		t.Fatalf("slm = %#v", slm)
	}
	if agg["harden"].(M)["converged"] != true {
		t.Fatal("harden not read")
	}
}
