PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: server agent analyzer test lint demo proto

proto:
	cd proto && bash compile.sh

server:
	$(PYTHON) -m server.app.main

agent:
	$(PYTHON) -m agent.mini_drop_agent.main

analyzer:
	$(PYTHON) -m analyzer.mini_drop_analyzer.hotmethod_analyzer \
		--task-id demo_task \
		--config analyzer/config.example.toml

test:
	$(PYTHON) -m pytest tests -v

lint:
	$(PYTHON) -m compileall server agent analyzer demo

demo:
	@echo "demo: run 'python demo/cpu_hotspot.py' first, then create a task via Web or API"
