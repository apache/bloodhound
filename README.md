# New Bloodhound

## Requirements

Bloodhound uses pipenv for development process.

If you have pip installed already, installation can be a simple as

```
pip install --user pipenv
```

For more information on installing and usage of pipenv, see
https://docs.pipenv.org/.

Once pipenv is installed, the remaining job of installing should be as simple
as

```
pipenv install
```

If this doesn't work, it should be done from the same directory as the
`Pipenv` file.

Though possibly annoying, the commands in this file will assume the use of
`pipenv` but not that the pipenv shell has been activated.

## Setup

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
pipenv python manage.py dumpdata bh-core --format=yaml --indent=2 > bh-core/fixtures/[fixture-name].yaml
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

If `$BIN_LOCATION` is on the system path, it should be possible to run the integration tests.

So, assuming the use of pipenv:

```
pipenv run python functional_tests.py
```

There are currently not many tests - those that are there are in place to test
the setup above and assume that there will be useful tests in due course.
