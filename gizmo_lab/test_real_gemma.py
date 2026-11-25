"""Opt-in Integrationstest gegen das echte lokale Modell: GIZMO_REAL_OLLAMA=1."""
import os
import unittest
from diagnose_gemma import main


@unittest.skipUnless(os.environ.get('GIZMO_REAL_OLLAMA')=='1','Echtes Ollama nur nach ausdruecklichem Opt-in')
class RealGemmaTest(unittest.TestCase):
    def test_synthetic_relation(self):
        self.assertEqual(main(),0)
