.PHONY: install clean link unlink

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

install: $(VENV)
	$(PIP) install -e .

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

clean:
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf build dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

link: install
	mkdir -p ~/.local/bin
	@echo '#!/bin/bash' > ~/.local/bin/mdview
	@echo 'exec "$(CURDIR)/$(VENV)/bin/mdview" "$$@"' >> ~/.local/bin/mdview
	chmod +x ~/.local/bin/mdview
	@echo "Linked mdview to ~/.local/bin/mdview"

unlink:
	rm -f ~/.local/bin/mdview
