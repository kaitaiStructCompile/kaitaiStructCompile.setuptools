#!/usr/bin/env python3
import sys
import unittest
from collections import OrderedDict
from pathlib import Path

from kaitaiStructCompile.setuptools import kaitaiHelper

testsDir = Path(__file__).parent.absolute()
parentDir = testsDir.parent.absolute()


inputDir = testsDir / "ksys"


class Test(unittest.TestCase):
	def testKaitai_keyword(self):
		outDir = testsDir / "output"
		ofn = "a.py"
		ofp = outDir / ofn
		testCfg = {
			"kaitai": {
				"formats": {
					ofn: {"path": "a.ksy"},
					# "postprocess":["permissiveDecoding"], #fucking jsonschema is broken
					# "flags": ["--ksc-json-output"] #fucking jsonschema is broken
				},
				"formatsRepo": {"localPath": testsDir / "formats", "update": False},
				"outputDir": outDir,
				"inputDir": inputDir,
				"search": True,
				"flags": {"readStoresPos": True, "opaqueTypes": True, "verbose": []},
			}
		}
		kaitaiHelper(None, None, testCfg["kaitai"])
		self.assertTrue(ofp.exists())


if __name__ == "__main__":
	unittest.main()
