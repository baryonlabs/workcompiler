// owc-inspect — a read-only local dashboard for verifying every layer of a compiled build:
// capture (trace), compile (tier map), bench (reproduction matrix), SLM gates, cache freshness,
// harden loop, ledger. Single binary, no external services; it only ever reads files.
//
//	go run ./tools/inspect -dir build -port 8890
package main

import (
	"embed"
	"encoding/json"
	"flag"
	"fmt"
	"io/fs"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

//go:embed static
var static embed.FS

func main() {
	dir := flag.String("dir", "build", "directory containing the compiled builds")
	catalog := flag.String("catalog", "examples/org/catalog.yaml", "decision catalog for the ontology view (optional)")
	port := flag.Int("port", 8890, "port to listen on")
	flag.Parse()

	base, err := filepath.Abs(*dir)
	if err != nil || !dirExists(base) {
		log.Fatalf("build directory not found: %s", *dir)
	}

	catalogPath, _ := filepath.Abs(*catalog)

	mux := http.NewServeMux()
	mux.HandleFunc("/api/builds", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, ListBuilds(base))
	})
	mux.HandleFunc("/api/catalog", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, LoadCatalog(catalogPath))
	})
	mux.HandleFunc("/api/build/", func(w http.ResponseWriter, r *http.Request) {
		name := strings.TrimPrefix(r.URL.Path, "/api/build/")
		name = filepath.Base(name) // no traversal
		root := filepath.Join(base, name)
		if !dirExists(root) {
			http.Error(w, "unknown build", http.StatusNotFound)
			return
		}
		writeJSON(w, Aggregate(root))
	})
	sub, _ := fs.Sub(static, "static")
	mux.Handle("/", http.FileServer(http.FS(sub)))

	addr := fmt.Sprintf("127.0.0.1:%d", *port)
	log.Printf("owc-inspect: serving %s on http://%s", base, addr)
	log.Fatal(http.ListenAndServe(addr, mux))
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func dirExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}
