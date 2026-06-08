import sys
sys.path.insert(0, "/repo/api")
from stores.db import engine
from sqlalchemy import text
with engine.connect() as cx:
    print(cx.execute(text("SELECT event, COUNT(*) FROM adoption_log GROUP BY event")).all())
