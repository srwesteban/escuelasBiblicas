PYTHON := ./.venv/bin/python
PIP := ./.venv/bin/pip

.PHONY: setup install migrate seed run check shell superuser

setup:
	python3.12 -m venv .venv
	$(PIP) install -r requirements.txt

install:
	$(PIP) install -r requirements.txt

migrate:
	$(PYTHON) manage.py migrate

seed:
	$(PYTHON) manage.py seed_local_data

run:
	$(PYTHON) manage.py runserver

check:
	$(PYTHON) manage.py check

shell:
	$(PYTHON) manage.py shell

superuser:
	$(PYTHON) manage.py createsuperuser
