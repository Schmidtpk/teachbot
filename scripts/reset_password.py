"""
IID-AUTH-BASIC
Password reset: removes a student's account, so their next login registers it again with a new
password. Accounts survive redeploys (Railway volume), so a forgotten password needs this.

    railway ssh --service teachbot-timeseries -- python scripts/reset_password.py student@stud.unibas.ch
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth import delete_user  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
email = sys.argv[1]
if not delete_user(email):
    sys.exit(f"No account for {email}.")
print(f"Removed {email}. Their next login sets a new password.")
