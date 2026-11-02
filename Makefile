.PHONY: eval bakeoff eval-live judge-calibrate pdf

eval:
	uv run python -m kb_evals

bakeoff:
	uv run python -m kb_evals.bakeoff

eval-live:
	@test -n "$$ANTHROPIC_API_KEY" || { echo "ANTHROPIC_API_KEY is required"; exit 1; }
	@test -n "$(ANSWERS)" || { echo "usage: make eval-live ANSWERS=path/to/answers.jsonl"; exit 1; }
	uv run python -m kb_evals.judge run --answers "$(ANSWERS)"

judge-calibrate:
	@test -n "$(RUN)" -a -n "$(LABELS)" || { echo "usage: make judge-calibrate RUN=evals/runs/x.jsonl LABELS=evals/labels/x.jsonl"; exit 1; }
	uv run python -m kb_evals.judge calibrate --run "$(RUN)" --labels "$(LABELS)"

pdf:
	uv run python evals/scripts/make_pdf.py
