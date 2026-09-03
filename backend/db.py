from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DATABASE_URL

# Neon silently closes idle connections after a while; without the settings
# below, long-running servers hand out dead pooled connections and requests
# fail with 'SSL connection has been closed unexpectedly' (or hang).
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # validate each connection on checkout; replace dead ones
    pool_recycle=280,     # recycle before server-side idle cutoffs
    connect_args={        # TCP keepalives so idle connections survive NAT/idle drops
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    },
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Keep the Neon compute awake: free-tier compute suspends after ~5 idle
# minutes, and the cold start turns the first dashboard request into a
# multi-second wait (or a 500 when a cold-start connection fails).
import threading, time as _time

def _keep_warm():
    while True:
        _time.sleep(45)
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
        except Exception:
            pass

threading.Thread(target=_keep_warm, daemon=True).start()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
