"""Reproduces two review findings on PostgreSQL 17: (1) a writing transaction in another database
holds back this database's snapshot xmin; (2) (xid, seq) order differs from commit order for one
Document when a writer took its xid before touching the Document."""
import psycopg

BASE = "postgresql://postgres:pw@localhost:55439/"
admin = psycopg.connect(BASE + "postgres", autocommit=True)
for name in ("a", "b"):
    admin.execute(f"CREATE DATABASE {name}")

# (1)
other = psycopg.connect(BASE + "b")
other.execute("CREATE TABLE t (x int)")  # a writing transaction, left open
other_xid = other.execute("SELECT pg_current_xact_id()::text").fetchone()[0]
a = psycopg.connect(BASE + "a", autocommit=True)
a.execute("CREATE TABLE feed (xid xid8 DEFAULT pg_current_xact_id(), seq serial, note text)")
a.execute("INSERT INTO feed (note) VALUES ('committed')")
visible = a.execute(
    "SELECT count(*) FROM feed WHERE xid < pg_snapshot_xmin(pg_current_snapshot())"
).fetchone()[0]
xmin = a.execute("SELECT pg_snapshot_xmin(pg_current_snapshot())::text").fetchone()[0]
print(f"(1) open writer in database b has xid {other_xid}; database a sees xmin {xmin};"
      f" committed feed rows readable: {visible}")
assert visible == 0 and xmin == other_xid
other.rollback()
assert a.execute(
    "SELECT count(*) FROM feed WHERE xid < pg_snapshot_xmin(pg_current_snapshot())"
).fetchone()[0] == 1

# (2)
a.execute("CREATE TABLE doc (uid text PRIMARY KEY, v text)")
a.execute("CREATE TABLE other (x int)")
a.execute("INSERT INTO doc VALUES ('d', '0')")
a.execute("TRUNCATE feed")
first, second = psycopg.connect(BASE + "a"), psycopg.connect(BASE + "a")
first.execute("INSERT INTO other VALUES (1)")  # takes its xid before touching the Document
second.execute("UPDATE doc SET v = 'second' WHERE uid = 'd'")
second.execute("INSERT INTO feed (note) VALUES ('second, committed first')")
second.commit()
first.execute("UPDATE doc SET v = 'first' WHERE uid = 'd'")
first.execute("INSERT INTO feed (note) VALUES ('first, committed last')")
first.commit()
order = [r[0] for r in a.execute("SELECT note FROM feed ORDER BY feed.xid, seq")]
state = a.execute("SELECT v FROM doc").fetchone()[0]
print(f"(2) feed order: {order}; final state: {state}")
assert order == ["first, committed last", "second, committed first"] and state == "first"
print("both findings reproduced")
