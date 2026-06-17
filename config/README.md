"""
config/
-------
Runtime configuration files that should NOT be committed to version control.

Files in this directory:
  credentials.json    — Google OAuth2 client credentials (download from Google Cloud Console)
  token.json          — OAuth2 access/refresh token (auto-generated on first run)
  skipped_senders.txt — One blocked sender email/domain per line (# for comments)
  skipped_threads.json — Persistent list of thread IDs permanently skipped by the agent
"""
