SHELL := /bin/bash
ROOT := $(shell pwd)
PYTHON ?= python3
VENV := $(ROOT)/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help install api web dev test lint build migrate revision seed collect

help:
	@echo "make install   创建 venv 并安装前后端依赖（PYTHON=python3.12 可指定解释器）"
	@echo "make dev       并行启动 API(8000) 与前端(5173)"
	@echo "make api       仅启动后端（热重载）"
	@echo "make web       仅启动前端"
	@echo "make test      运行后端测试"
	@echo "make lint      运行 ruff"
	@echo "make migrate   执行 Alembic 升级"
	@echo "make seed      重建数据库并写入演示数据（会删除现有数据）"
	@echo "make build     构建前端产物"

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	cd frontend && npm install

api:
	cd backend && $(PY) -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

web:
	cd frontend && npm run dev

dev:
	bash scripts/dev.sh

test:
	cd backend && $(PY) -m pytest -q

lint:
	cd backend && $(VENV)/bin/ruff check app tests

build:
	cd frontend && npm run build

migrate:
	cd backend && $(VENV)/bin/alembic upgrade head

revision:
	cd backend && $(VENV)/bin/alembic revision --autogenerate -m "$(m)"

seed:
	rm -f backend/data/board.db backend/data/board.db-wal backend/data/board.db-shm
	cd backend && $(PY) -c "from app.db.init_db import init_db; init_db(seed=True)"

collect:
	curl -s -X POST http://127.0.0.1:8000/api/system/collect | $(PY) -m json.tool
