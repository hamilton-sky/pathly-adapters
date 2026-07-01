# create-feature

Create one or more Pathly feature boards. A feature is a first-class workspace at
`pathly/features/<name>/` with its own scoped board. Use this to stand up features quickly:
each gets a workspace and a board seeded with a root goal.

## Parse the request

`$ARGUMENTS` names one or more features to create. A feature spec is a name, optionally with a
one-line description after a colon (`invoice-export: CSV export for invoices`). Create every
feature the user listed — if they asked for several, loop over all of them.

## For each feature

1. **Slugify the name** — lowercase, hyphen-separated, filesystem-safe. It must NOT be a
   reserved structural name (see the fragment's list). Slugify or suffix anything that collides.
2. **Create the board** — follow the "Creating a feature board" steps composed below. That
   posts the feature's root goal, which materializes the board and its Studio card; reuse the
   goal if one already exists.
3. **Create the workspace** `pathly/features/<name>/plans/` if it is absent.

## Report

One line per feature: `name · $GOAL_ID · workspace path · (created | reused | renamed-from-…)`.
State the total created and any skipped or renamed.
