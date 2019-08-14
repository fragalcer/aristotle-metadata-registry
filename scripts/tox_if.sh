#!/bin/bash
# This script was having issues and is currently not being used
TOX_ENV_TO_RUN=$1

# Setup git for diff as per https://github.com/travis-ci/travis-ci/issues/6069
git remote set-branches --add origin $TRAVIS_BRANCH
git fetch

if [ "$TRAVIS_BRANCH" = "master" ] || ./scripts/check_path.sh $MODULE_PATH || ./scripts/check_path.sh python/aristotle-metadata-registry; then
  tox -e $TOX_ENV_TO_RUN --skip-missing-interpreters
  export OUT_CODE=$?
fi;

exit $OUT_CODE
