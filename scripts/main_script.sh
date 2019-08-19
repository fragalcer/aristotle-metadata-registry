#!/usr/bin/env bash
set -ev
case "$DB" in
mariadb)
  export DATABASE_URL=mysql://travis:@localhost:3306/aristotle_test_db;;
postgres)
  export DATABASE_URL=postgresql://postgres:@localhost/aristotle_test_db;;
sqlite)
  export DATABASE_URL=sqlite:///./db.db;;
*)
  export DATABASE_URL=sqlite:///./db.db;;
esac
echo "Running script with DATABASE_URL="$DATABASE_URL
echo "Running script with DB="$DB
tox -e dj-test-linux-db-$DB-search-$SEARCH-module_$MODULE