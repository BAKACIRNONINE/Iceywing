install:
    python -m pip install -e .

test:
    python -m pytest
verify:
    python -m compileall -q src tests
    just test
doctor:
    python --version
    git --version
    just --version
    python -m iceywing --help
