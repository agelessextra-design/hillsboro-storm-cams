#!/bin/bash
# Publishes site/ plus the page to the gh-pages branch as a single commit.
set -e
cp web/index.html site/index.html
cp schedule.json site/schedule.json
rm -rf site/wxraw site/.git
touch site/.nojekyll
cd site
git init -q
git checkout -q -b gh-pages
git config user.name "storm-collector"
git config user.email "storm-collector@users.noreply.github.com"
git add -A
git commit -q -m "Collected $(date -u +%Y-%m-%dT%H:%MZ)"
git push -q --force "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" gh-pages
