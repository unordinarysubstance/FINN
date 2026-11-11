"""The portable public index must never overwrite an existing investor workspace."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import store

class PublicSeedTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
  self.context=patch.multiple(store,ROOT=self.root,DATA=self.root/'runtime');self.context.start()
  self.env=patch.dict(os.environ,{'FINN_DISABLE_DEMO_SEED':'0'});self.env.start()
  (self.root/'demo_data').mkdir();(self.root/'demo_primary').mkdir()
  (self.root/'demo_primary'/'public.pdf').write_bytes(b'%PDF-public-fixture')
 def tearDown(self):
  self.env.stop();self.context.stop();self.temp.cleanup()
 def template(self,relative='demo_primary/public.pdf'):
  with sqlite3.connect(self.root/'demo_data'/'public.sqlite3') as c:
   c.execute('CREATE TABLE documents(id TEXT PRIMARY KEY,path TEXT)')
   c.execute('INSERT INTO documents VALUES (?,?)',('public',relative))
 def test_installs_portable_paths_and_leaves_template_unchanged(self):
  self.template();store.install_public_seed()
  with sqlite3.connect(store.DATA/'finn.sqlite3') as c:
   self.assertEqual(c.execute('SELECT path FROM documents').fetchone()[0],str((self.root/'demo_primary'/'public.pdf').resolve()))
  with sqlite3.connect(self.root/'demo_data'/'public.sqlite3') as c:
   self.assertEqual(c.execute('SELECT path FROM documents').fetchone()[0],'demo_primary/public.pdf')
  self.assertEqual(list(store.DATA.glob('.public-seed-*')),[])
 def test_existing_investor_database_is_never_replaced(self):
  self.template();store.DATA.mkdir();target=store.DATA/'finn.sqlite3'
  target.write_bytes(b'existing investor state');store.install_public_seed()
  self.assertEqual(target.read_bytes(),b'existing investor state')
 def test_rejects_private_absolute_traversal_empty_and_missing_paths(self):
  (self.root/'.env').write_text('private-fixture')
  for relative in ('.env','demo_primary/../.env',str(self.root/'demo_primary'/'public.pdf'),'','demo_primary/missing.pdf'):
   with self.subTest(path=relative):
    (self.root/'demo_data'/'public.sqlite3').unlink(missing_ok=True);self.template(relative)
    with self.assertRaises(ValueError):store.install_public_seed()
    self.assertFalse((store.DATA/'finn.sqlite3').exists())
    self.assertEqual(list(store.DATA.glob('.public-seed-*')),[])
 def test_seed_can_be_disabled_for_isolated_tools_and_tests(self):
  self.template()
  with patch.dict(os.environ,{'FINN_DISABLE_DEMO_SEED':'1'}):store.install_public_seed()
  self.assertFalse((store.DATA/'finn.sqlite3').exists())
