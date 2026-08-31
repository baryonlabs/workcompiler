// Ontology-catalog view: read the declarative decision catalog (cases with ontology,
// features, ordered rules, defer bands, fallback) so the dashboard can render how the
// organization's judgment is structured — read-only, like every other layer.
package main

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// LoadCatalog parses catalog.yaml and attaches the sibling decision-slm eval report
// (markdown, if present) so the view can show how well the trained model applies it.
func LoadCatalog(path string) M {
	data, err := os.ReadFile(path)
	if err != nil {
		return M{"present": false}
	}
	var doc M
	if yaml.Unmarshal(data, &doc) != nil {
		return M{"present": false}
	}
	out := M{"present": true, "cases": doc["cases"], "path": path}
	report := filepath.Join(filepath.Dir(path), "decision-slm", "eval_report.md")
	if txt, err := os.ReadFile(report); err == nil {
		out["eval_report"] = string(txt)
	}
	return out
}
