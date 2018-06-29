Testing
=======

Aristotle uses tox and django's unit test framework for testing

Running tests locally
---------------------

Docker
^^^^^^

For running tests on a local docker environemnt refer to https://github.com/aristotle-mdr/aristotle-metadata-registry/docker

Tox
^^^

Tests can be run locally running tox with an optional environment argument e.g. ``tox -e dj1.11-test-linux-db-sqlite-search-whoosh``.

Virtualenv
^^^^^^^^^^

* To run tests in a virtualenv, first set the ``DJANGO_SETTINGS_MODULE`` enviroment variable to the settings module you want to use 
* Install dev requirements with ``pipenv install --dev``
* Run tests with ``pipenv run django-admin test aristotle_mdr``. Replacing aristotle_mdr with a full test path if needed

Adding extension modules to our automated testing
-------------------------------------------------

When adding an extension package to the system it is important to integrate this with the automated testing process to
ensure it is tested alongside the rest of the system

Once the extension has been added to the ``/python`` directory follow these steps to enable automated testing

#. Add a ``setup.py`` for your package with dependancies defined in install_requires
#. Add the package to the Pipfile at the base directory of the repo
#. Run ``pipenv lock`` to update the lock file
#. Add a new model extension to the envlist in ``tox.ini`` at the base directory of the repo
#. Define your settings module, module name and module path in the setenv section of ``tox.ini``
#. Add a new stage in ``.travis.yml`` with your new module extension

Done, your module will now be tested by travis automatically using the command ``django-admin test modulename``
