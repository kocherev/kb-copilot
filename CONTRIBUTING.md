# Contributing

1. Copy `.env.example` to `.env` if you need compose. Do not commit `.env`.
2. Branch from `main`.
3. Add a test that fails when the behavior you changed breaks. Assert what a caller can observe.
4. Run `./scripts/check.sh` before opening a pull request.

Pull requests land on `main`. Keep the diff to the behavior you are changing.
