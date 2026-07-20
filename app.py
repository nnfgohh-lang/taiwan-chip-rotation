"""Streamlit Cloud entry point.

The implementation lives in app_main.py so deployments cannot accidentally mix
the new entry point with an older cached analysis_v3 module.
"""

from app_main import *  # noqa: F401,F403
