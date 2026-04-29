.PHONY: help install test lint judge-demo judge-demo-offline clean

help:
	@echo "storyboard — Hermes Agent skill"
	@echo ""
	@echo "Common commands:"
	@echo "  make install            install package + dev deps"
	@echo "  make test               run smoke tests (no Kimi calls)"
	@echo "  make lint               ruff check"
	@echo "  make judge-demo         run a full live-stream demo (requires OPENROUTER_API_KEY)"
	@echo "  make judge-demo-offline render shipped example without any API call"
	@echo "  make clean              remove caches and build artefacts"

install:
	pip install -e '.[dev]'
	@echo ""
	@echo "Install librsvg2-bin (Ubuntu) or librsvg (macOS) for SVG to PNG export."
	@echo "Or: pip install cairosvg --break-system-packages"

test:
	pytest tests/test_smoke.py -v

lint:
	ruff check scripts tests

# Live demo — requires OPENROUTER_API_KEY. Streams the noir scene to a
# local viewer at http://localhost:7777, then waits for the user to
# Ctrl+C. This is the WOW path — recommended for video recording.
judge-demo:
	@if [ -z "$$OPENROUTER_API_KEY" ]; then \
		echo "OPENROUTER_API_KEY not set. Use 'make judge-demo-offline' for a no-key path."; \
		exit 1; \
	fi
	@echo "Open http://localhost:7777 in Firefox in the next 3 seconds."
	python -m scripts.storyboard full --stream \
		"A detective enters a rain-soaked alley at night. He walks past silent buildings, dispatch crackling in his ear. He finds a body. He kneels, recognises the knot at the wrist — the same one as last week. He straightens, calls his partner: \"Marlowe. Third one this month.\""

# Offline demo — re-renders the shipped noir-run example WITHOUT any
# Kimi calls. The Scene JSON is already parsed and committed; this just
# proves the renderer chain (parse → render → packet → viewer) works
# on a judge's machine even without an API key.
judge-demo-offline:
	@echo "Rendering the shipped noir example (no API call needed)..."
	@mkdir -p ~/storyboard-output
	@cp examples/output/noir-run/scene.v2.json ~/storyboard-output/scene.v2.json
	@cp examples/output/noir-run/scene.json ~/storyboard-output/scene.json
	@cp examples/output/noir-run/character_bible.json ~/storyboard-output/character_bible.json
	python -m scripts.storyboard render examples/output/noir-run/scene.v2.json \
		-o ~/storyboard-output/board.svg
	python -m scripts.storyboard packet examples/output/noir-run/scene.v2.json
	@echo ""
	@echo "Done. Outputs in ~/storyboard-output/"
	@echo "Open ~/storyboard-output/board.svg in Firefox to see the static render."
	@echo "For the live-drawing version: examples/output/noir-run/board.animated.svg"
	@echo "For the learning-loop demo: examples/output/learning-demo/cold-vs-directed.png"

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
