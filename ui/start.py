import os
import sys

from streamlit.web import cli

sys.argv = [
    "streamlit",
    "run",
    "ui/app.py",
    "--server.address=0.0.0.0",
    f"--server.port={os.getenv('PORT', '8501')}",
    "--server.headless=true",
    "--browser.gatherUsageStats=false",
]
sys.exit(cli.main())
