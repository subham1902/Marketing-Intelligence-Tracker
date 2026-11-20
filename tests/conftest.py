"""Shared test setup."""

import os

# Never auto-seed (subprocess + dbt) inside tests.
os.environ["COMPETE_AUTOSEED"] = "0"
