"""
Entrypoint for Iyobo's assistant as a Vercel service.

vercel.json runs this folder as the "iyobo" service and routes /iyobo and /iyobo/* on the website's
domain to it. Vercel passes the original path, so the app is told it lives under /iyobo; requests
without the prefix still route too. Locally and in Docker, run app.main:app as before.
"""

from app.main import app

SERVICE_PATH = "/iyobo"
app.root_path = SERVICE_PATH
