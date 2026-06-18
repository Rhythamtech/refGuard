import pathlib
import sqlite3
from datetime import datetime

class SqliteOrderDB:
    """
    An in-memory SQLite database wrapper to simulate fetching order data.
    In production, this would connect to PostgreSQL/CockroachDB.
    """

    def __init__(self):
        self.path = pathlib.Path(__file__).parent.parent / "refund-guard-db.sql"
        self.conn = None  
        self.cursor = None
        self.queries = self._read_sql_file()


    def connect_to_db(self):
        """Return a connection to the SQLite database."""
        db_path = pathlib.Path(__file__).parent.parent / "mock.db"
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.create_function("now", 0, lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.cursor = self.conn.cursor()

        self.conn.commit()
        
        return self.conn,self.cursor

    def _read_sql_file(self):
        """Read the SQL file."""
        with open(self.path, "r") as f:
            return f.read()
    
    def setup_db(self):
        """Setup the database."""
        if self.queries.strip():
            self.cursor.executescript(self.queries)
        self.conn.commit()

if "__main__" == __name__:
    db = SqliteOrderDB()
    db.connect_to_db()
    db.setup_db()