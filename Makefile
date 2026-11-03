.PHONY: eval bakeoff eval-answers eval-live judge-calibrate pdf

eval:
	uv run python -m kb_evals

bakeoff:
	uv run python -m kb_evals.bakeoff

ANSWERS ?= evals/runs/answers.jsonl
# Keys come from the repo .env when there is one. A variable set in the shell
# wins. Each command exits with a message when its key is missing.
WITH_ENV = $(if $(wildcard .env),--env-file .env)

eval-answers:
	uv run $(WITH_ENV) python -m kb_evals.answers --out "$(ANSWERS)"

eval-live:
	uv run $(WITH_ENV) python -m kb_evals.judge run --answers "$(ANSWERS)"

judge-calibrate:
	@test -n "$(RUN)" -a -n "$(LABELS)" || { echo "usage: make judge-calibrate RUN=evals/runs/x.jsonl LABELS=evals/labels/x.jsonl"; exit 1; }
	uv run python -m kb_evals.judge calibrate --run "$(RUN)" --labels "$(LABELS)"

pdf:
	uv run python evals/scripts/make_pdf.py
