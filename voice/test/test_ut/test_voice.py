# test_voice.py
# C:\Users\lars\python_venvs\packages\voice_audio\voice\test\test_ut\test_voice.py

import logging
import os
import unittest
import yaml

from voice.voice import DefaultClass
from voice.helpers.function_to_json import FunctionToJson
import voice.settings as sts

class Test_DefaultClass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verbose = 0

    @classmethod
    def tearDownClass(cls):
        pass

    @FunctionToJson(schemas={"openai"}, write=True)
    def test___str__(self):
        pc = DefaultClass(pr_name="voice_audio", pg_name="voice", py_version="3.7")
        expected = "DefaultClass: self.pg_name = 'voice'"
        self.assertEqual(str(pc), expected)
        logging.info("Info level log from the test")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
