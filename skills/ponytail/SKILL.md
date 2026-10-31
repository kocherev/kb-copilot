# Smaller diffs

Based on the Ponytail rules, MIT, https://github.com/DietrichGebert/ponytail.

Before writing, read the task and the code it touches. List every place the change must reach. That list is the scope.

Take the first option that fully works:

1. Does it need to exist? Skip features nobody asked for, and name what you skipped.
2. Is there already a helper, component, or pattern here? Use it the way the surrounding code does.
3. Will the standard library or the platform do it? Use that, unless this repo already has its own.
4. Is the dependency already installed? Use it. Do not add a dependency for a few lines.
5. Can it be one line a reader gets at a glance? One line.
6. Otherwise write the minimum that works.

Finish every part the task needs, including callers and tests your change breaks. Deletion beats a new wrapper. Comment only a why the code cannot show, in one line.

A shortcut with a known limit gets a comment in this form: `shortcut: <limit>. Revisit when <condition>.`

Lazy code without its check is unfinished. A branch, a loop, a parser, money, security, or a new script leaves one small test.

Never cut validation at trust boundaries, error handling that prevents data loss, security, or accessibility.

End the note for the change with what you did not run, and any risk that remains.
