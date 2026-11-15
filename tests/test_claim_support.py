import unittest
from research import checked_findings,page_evidence
from unittest.mock import patch

class ClaimSupportTests(unittest.TestCase):
 def setUp(self):
  self.citations=[{'id':'S1','period':'FY2026','excerpt':'Consolidated revenue was 10 crore in FY2026. Demand remained weak.'},
                  {'id':'S2','period':'FY2026','excerpt':'Working capital was 40 crore. The company had no outstanding borrowings.'}]
 def check(self,text,quote,source='S1',supported=True):
  return checked_findings([{'text':text,'sources':['S1']}],{'checks':[{'index':0,'supported':supported,'supports':[{'source':source,'quote':quote}]}]},self.citations)
 def test_exact_support_is_retained_with_auditable_quote(self):
  accepted,rejected=self.check('Consolidated revenue was 10 crore in FY2026.','Consolidated revenue was 10 crore in FY2026.')
  self.assertEqual(rejected,[]);self.assertEqual(accepted[0]['support_quotes'][0]['source'],'S1')
 def test_invented_quote_is_rejected_even_if_reviewer_approves(self):
  accepted,rejected=self.check('Revenue doubled.','Consolidated revenue doubled to 20 crore in FY2026.')
  self.assertEqual(accepted,[]);self.assertEqual(len(rejected),1)
 def test_reviewer_cannot_switch_to_an_uncited_source(self):
  accepted,_=self.check('The company had no outstanding borrowings.','The company had no outstanding borrowings.',source='S2')
  self.assertEqual(accepted,[])
 def test_missing_numeric_support_is_rejected(self):
  accepted,rejected=self.check('Consolidated revenue was 99 crore in FY2026.','Consolidated revenue was 10 crore in FY2026.')
  self.assertEqual(accepted,[]);self.assertIn('numerical literal',rejected[0]['reason'])
 def test_false_or_missing_decision_never_approves(self):
  self.assertEqual(self.check('Revenue was 10 crore.','Consolidated revenue was 10 crore in FY2026.',supported=False)[0],[])
  accepted,rejected=checked_findings([{'text':'Claim','sources':['S1']}],{'checks':[]},self.citations)
  self.assertEqual(accepted,[]);self.assertEqual(len(rejected),1)
 def test_duplicate_or_boolean_indexes_are_invalid(self):
  for checks in [[{'index':True,'supported':True}], [{'index':0,'supported':True},{'index':0,'supported':False}]]:
   with self.assertRaises(ValueError):checked_findings([{'text':'Claim','sources':['S1']}],{'checks':checks},self.citations)
 def test_page_context_restores_heading_and_avoids_overlap_duplication(self):
  first='Consolidated statement. '+'Cash flows before working capital changes 68,688. '*20
  second=first[-100:]+' Net operating cash flow 52,094.'
  with patch('research.rows',return_value=[{'text':first},{'text':second}]):
   text=page_evidence({'document_id':'doc','page':1,'text':second})
  self.assertTrue(text.startswith('Consolidated statement.'))
  self.assertEqual(text,first+' Net operating cash flow 52,094.')
 def test_cash_question_prefers_statement_over_contents_or_liquidity_note(self):
  import store
  import tempfile
  from pathlib import Path
  from types import SimpleNamespace
  temp=tempfile.TemporaryDirectory();old=store.DATA;store.DATA=Path(temp.name)
  try:
   store.init(seed_demo=False)
   texts=['Contents\nConsolidated Statement of Cash Flows\nLiquidity risk, debt, profit and operating cash flows are discussed elsewhere. '*5,
          'Consolidated Statement of Cash Flows\nFY2026 FY2025\nProfit for the year 100 90\nOperating cash flows after taxes 120 110\nWorking capital changes 20 15\n'+'Business operations and annual cash flow discussion. '*8]
   reader=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda text=text:text) for text in texts])
   with patch.object(store,'PdfReader',return_value=reader):store.import_pdf(b'%PDF-fixture','NEWCO','Annual','annual_report','FY2026')
   answer=store.retrieve('NEWCO','How does operating cash flow compare with profit and debt?')
   self.assertEqual(answer[0]['page'],2)
  finally:store.DATA=old;temp.cleanup()
 def test_fiscal_year_and_pdf_spacing_do_not_reject_same_value(self):
  from research import numbers_supported,normalise_quote
  self.assertTrue(numbers_supported('FY2025 net operating cash flow was 48,908 crore.','FY 2024-25\nNet operating cash flow 48, 908','FY2026'))
  self.assertTrue(numbers_supported('FY2026 cash generated was 66,478 crore.','Cash generated 66, 47 8','FY2026'))
  self.assertEqual(normalise_quote('N et cash flows 52, 094'),normalise_quote('Net cash flows 52,094'))
  self.assertFalse(numbers_supported('Revenue was 99 crore.','Revenue was 199 crore.','FY2026'))
 def test_reviewer_can_narrow_a_claim_without_bypassing_support(self):
  findings=[{'text':'Revenue was 99 crore and demand will double.','sources':['S1'],'kind':'fact'}]
  checked={'checks':[{'index':0,'supported':True,'text':'Consolidated revenue was 10 crore in FY2026.','kind':'fact','supports':[{'source':'S1','quote':'Consolidated revenue was 10 crore in FY2026.'}]}]}
  accepted,rejected=checked_findings(findings,checked,self.citations)
  self.assertEqual(rejected,[]);self.assertTrue(accepted[0]['revised'])
  self.assertNotIn('double',accepted[0]['text'])
  checked['checks'][0]['text']='Consolidated revenue was 99 crore in FY2026.'
  self.assertEqual(checked_findings(findings,checked,self.citations)[0],[])
 def test_rejections_keep_draft_and_quote_for_debugging(self):
  accepted,rejected=self.check('Revenue was 99 crore.','Consolidated revenue was 10 crore in FY2026.')
  self.assertEqual(accepted,[]);self.assertEqual(rejected[0]['draft_text'],'Revenue was 99 crore.')
  self.assertEqual(len(rejected[0]['supports']),1)
 def test_real_failure_replayed_with_two_source_line_ranges(self):
  excerpt='Consolidated Statement of Cash Flows\n(H crore)\nYear ended March 31, 2026\nProfit for the year 49,454 48,797\nAdjustments for depreciation and working capital\nTaxes paid (14,384) (15,586)\nNet cash flows generated from operating activities 52, 094 48, 908'
  citations=[{'id':'S1134','period':'FY2026','excerpt':excerpt}]
  findings=[{'text':'Profit was 49,454 crore and operating cash flow was 52,094 crore in FY2026.','sources':['S1134'],'kind':'fact'}]
  check={'index':0,'supported':True,'text':'Consolidated FY2026 profit was 49,454 crore and net operating cash flow was 52,094 crore.','kind':'fact','supports':[{'source':'S1134','start_line':1,'end_line':4},{'source':'S1134','start_line':7,'end_line':7}]}
  accepted,rejected=checked_findings(findings,{'checks':[check]},citations)
  self.assertEqual(rejected,[]);self.assertEqual(len(accepted[0]['support_quotes']),2)
  self.assertIn('48, 908',accepted[0]['support_quotes'][1]['quote'])
  check['supports'][0]['source']='S1'
  accepted,rejected=checked_findings(findings,{'checks':[check]},citations)
  self.assertEqual(accepted,[]);self.assertIn('source not cited',rejected[0]['reason'])
  self.assertNotIn('numerical literal',rejected[0]['reason'])
 def test_line_range_bounds_are_checked(self):
  for start,end in [(0,1),(1,99),(2,1),(True,1)]:
   check={'index':0,'supported':True,'supports':[{'source':'S1','start_line':start,'end_line':end}]}
   accepted,rejected=checked_findings([{'text':'Revenue was 10 crore.','sources':['S1']}],{'checks':[check]},self.citations)
   self.assertEqual(accepted,[]);self.assertIn('invalid source line range',rejected[0]['reason'])
 def test_structured_review_schema_uses_actual_source_ids(self):
  from research import reviewer_format
  fmt=reviewer_format({'S1134'},1)
  self.assertEqual(fmt['type'],'json_schema');self.assertTrue(fmt['strict'])
  check=fmt['schema']['properties']['checks']['items']
  self.assertEqual(check['properties']['supports']['items']['properties']['source']['enum'],['S1134'])
  self.assertEqual(check['properties']['index']['enum'],[0])
  self.assertFalse(check['additionalProperties'])
 def test_analyst_schema_requires_object_and_limits_source_ids(self):
  from research import analyst_format
  schema=analyst_format({'S42','S1134'})['schema']
  self.assertEqual(schema['type'],'object');self.assertFalse(schema['additionalProperties'])
  finding=schema['properties']['findings']['items']
  self.assertEqual(set(finding['required']),{'text','kind','sources'})
  self.assertEqual(finding['properties']['sources']['items']['enum'],['S1134','S42'])
