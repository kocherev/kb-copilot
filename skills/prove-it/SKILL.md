# Prove it

A change is done when a command you can rerun shows the behavior.

- Call the route, render the screen, or parse the file. "It typechecks" is a separate check.
- Keep the check in the repo when it can run without a private account.
- Prefer a test over a one-time manual step when the behavior is local.
- If a check did not run, name the command and why it did not run.

For this repo, `./scripts/check.sh` covers lint, types, unit tests, and `docker compose config`. A compose config check does not prove the containers boot. Say so when you have not run `docker compose up`.
