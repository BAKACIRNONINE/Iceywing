install:
    python -m pip install -e .

test:
    python -m unittest discover -s tests -v

verify:
    python -m compileall -q src
    just test

doctor:
    python --version
    git --version
    just --version
    python -m iceywing --help
