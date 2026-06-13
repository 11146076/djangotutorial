"""Gunicorn WSGI 設定 — 載入 mysite.wsgi:application"""

import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "unix:/run/eatwhat/gunicorn.sock")
workers = int(os.environ.get("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

wsgi_app = "mysite.wsgi:application"
chdir = os.environ.get("GUNICORN_CHDIR", "/srv/eatwhat/app")
umask = 0o007
