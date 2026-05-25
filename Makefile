# Thin delegator to justfile — provided for muscle memory.
# Canonical recipes live in `justfile`. Edit there, not here.

.DEFAULT_GOAL := help

%:
	@just $@

help:
	@just --list
