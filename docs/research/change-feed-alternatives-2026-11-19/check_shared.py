"""On an instance with transaction_timeout set for the whole instance, a writer left open in
another database is ended and this database's feed becomes readable again; a role may be exempted."""
import time

import psycopg

BASE = "postgresql://postgres@localhost:55439/"
admin = psycopg.connect(BASE + "postgres", autocommit=True)
for name in ("a", "b"):
    admin.execute(f"CREATE DATABASE {name}")
admin.execute("CREATE ROLE migrator LOGIN SUPERUSER")
admin.execute("ALTER ROLE migrator SET transaction_timeout = 0")
print("instance setting:", admin.execute("SHOW transaction_timeout").fetchone()[0])

a = psycopg.connect(BASE + "a", autocommit=True)
a.execute("CREATE TABLE feed (xid xid8 DEFAULT pg_current_xact_id(), seq serial, note text)")
READABLE = "SELECT count(*) FROM feed WHERE xid < pg_snapshot_xmin(pg_current_snapshot())"

other = psycopg.connect(BASE + "b")
other.execute("CREATE TABLE t (x int)")  # a writer in another database, left open
a.execute("INSERT INTO feed (note) VALUES ('committed')")
print("while the other database's writer is open:", a.execute(READABLE).fetchone()[0])
time.sleep(3)
print("after the instance timeout ended it:", a.execute(READABLE).fetchone()[0])

exempt = psycopg.connect("postgresql://migrator@localhost:55439/b")
exempt.execute("CREATE TABLE u (x int)")
a.execute("INSERT INTO feed (note) VALUES ('second')")
time.sleep(3)
print("exempt role still open after 3 s, readable rows:", a.execute(READABLE).fetchone()[0], "of 2")
exempt.rollback()
print("after the exempt role ends:", a.execute(READABLE).fetchone()[0], "of 2")
