PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

.PHONY: server agent analyzer test coverage lint demo proto deploy deploy-down

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

coverage:
	$(PYTHON) -m pytest --cov=server --cov=agent --cov=analyzer --cov-report=term-missing tests

lint:
	$(PYTHON) -m compileall server agent analyzer demo

demo:
	bash demo/demo.sh

deploy:
	docker compose up -d

deploy-down:
	docker compose down
