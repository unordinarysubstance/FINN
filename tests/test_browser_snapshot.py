import sqlite3
import tempfile
from pathlib import Path
import unittest
from browser_qa import clone_database

class BrowserSnapshotTests(unittest.TestCase):
 def test_qa_backup_includes_search_and_does_not_mutate_source(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp)/'source.sqlite3';destination=Path(temp)/'qa'/'finn.sqlite3'
   with sqlite3.connect(source) as c:
    c.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,saved INTEGER)')
    c.execute('INSERT INTO state VALUES (1,0)')
    c.execute('CREATE VIRTUAL TABLE search USING fts5(text)')
    c.execute("INSERT INTO search VALUES ('company cash flow')")
   clone_database(source,destination)
   with sqlite3.connect(destination) as c:
    self.assertEqual(c.execute("SELECT count(*) FROM search WHERE search MATCH 'cash'").fetchone()[0],1)
    c.execute('UPDATE state SET saved=1')
   with sqlite3.connect(source) as c:self.assertEqual(c.execute('SELECT saved FROM state').fetchone()[0],0)
