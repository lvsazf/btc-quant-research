import ast, unittest
from pathlib import Path
class MarkRequestTest(unittest.TestCase):
 def test_mark_request_uses_documented_lowercase(self):
  tree=ast.parse((Path(__file__).parents[1]/'run_research.py').read_text())
  values=[k.value.value for n in ast.walk(tree) if isinstance(n,ast.Call) for k in n.keywords if k.arg=='kLineType' and isinstance(k.value,ast.Constant)]
  self.assertIn('mark',values)
  self.assertNotIn('MARK',values)
