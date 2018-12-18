# New Bloodhound

## Requirements

### Python

Bloodhound core is currently written in Python3. It should be possible to
install and run the core successfully with Python 3.6 or newer. You may
find that versions from Python 3.4 work but this is not currently tested
and it is possible that Python features from newer versions may sneak in.

If you do not already have an appropriate version of Python installed, you
may wish to follow instructions for your platform here:

  https://docs.python-guide.org/starting/installation/

### Pipenv

Pipenv is used for looking after Python package dependencies and virtual
environment management.

If you already have the `pip` program installed already, installation of
pipenv can be as simple as

```
pip install --user pipenv
```

For more information on installing and usage of pipenv, see
https://docs.pipenv.org/.

Once pipenv is installed, the final bit of setup ahead of installing the
rest of the project dependencies is to ensure that you have picked out the
appropriate version of Python for your environment. For the same directory
as the `Pipfile` for the project, you should run:

```
pipenv --python 3
```

If you have multiple versions of Python 3 installed, you may need to be
more specific about the version.

### Pipfile Specified Requirements

With pipenv installed and the Python version selected, the rest of the
Python based requrements can be installed with the following command from
the same director as the `Pipfile` for the project:

```
pipenv install
```

Additionally, to run tests described later, you should install the
development dependencies:

```
pipenv install --dev
```

## Setup

Although it will make the commands more verbose, where a command requires
the pipenv environment that has been created, we will use the `pipenv run`
command in preference to requiring that the environment is 'activated'.

The basic setup steps to get running are:

```
pipenv run python manage.py makemigrations trackers
pipenv run python manage.py migrate
```

The above will do the basic database setup.

Note that currently models are in flux and, for the moment, no support should
be expected for migrations as models change. This will change when basic
models gain stability.

## Running the development server:

```
pipenv run python manage.py runserver
```

## Unit Tests

Unit tests are currently being written with the standard unittest framework.
This may be replaced with pytest.

The tests may be run with the following command:

```
pipenv run python manage.py test
```

Fixtures for tests when required can be generated with:

```
pipenv run python manage.py dumpdata trackers --format=yaml --indent=2 > trackers/fixtures/[fixture-name].yaml
```

## Integration Tests

Selenium tests currently require that Firefox is installed and `geckodriver` is
also on the path. One way to do this is (example for 64bit linux distributions):

```
BIN_LOCATION="$HOME/.local/bin"
PLATFORM_EXT="linux64.tar.gz"
TMP_DIR=/tmp
LATEST=$(wget -O - https://github.com/mozilla/geckodriver/releases/latest 2>&1 | awk 'match($0, /geckodriver-(v.*)-'"$PLATFORM_EXT"'/, a) {print a[1]; exit}')
wget -N -P "$TMP_DIR" "https://github.com/mozilla/geckodriver/releases/download/$LATEST/geckodriver-$LATEST-$PLATFORM_EXT"
tar -x geckodriver -zf "$TMP_DIR/geckodriver-$LATEST-$PLATFORM_EXT" -O > "$BIN_LOCATION"/geckodriver
chmod +x "$BIN_LOCATION"/geckodriver
```

If `$BIN_LOCATION` is on the system path, and the development server is
running, it should be possible to run the integration tests.

```
pipenv run python functional_tests.py
```

There are currently not many tests - those that are there are in place to test
the setup above and assume that there will be useful tests in due course.
