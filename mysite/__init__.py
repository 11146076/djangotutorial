import os

# Only when USE_MYSQL=1 (MariaDB/MySQL). Otherwise settings use SQLite and PyMySQL is not needed.
if os.environ.get("USE_MYSQL", "").strip().lower() in ("1", "true", "yes"):
    import pymysql

    pymysql.install_as_MySQLdb()

    # Django 5.2+ requires mysqlclient >= 2.2.1; PyMySQL's MySQLdb shim reports 1.4.x.
    import MySQLdb

    MySQLdb.version_info = (2, 2, 1, "final", 0)

try:
    from .celery import app as celery_app
except Exception:  # pragma: no cover
    celery_app = None

__all__ = ("celery_app",)
