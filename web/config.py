import os
import sys

# Ensure project root is importable when running `streamlit run web/app.py`
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from project_config import SETTINGS


API_BASE_URL = SETTINGS.api_base_url
