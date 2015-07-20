#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
import unittest
from unical import Schedule
import codecs

class TestRefParser(unittest.TestCase):
    """
    unit tests
    """

    def setUp(self):
        pass

    def get_file(self, name):
        with open(name, "r") as myfile:
            return myfile.read()

    def _equal(self, txt, html):
        f = open("raum1171.txt", "w")
        text = Schedule(self.get_file(html)).__str__().encode("utf-8").strip()
        print(text)
        f.write(str(text))
        f.close()
        self.assertEqual(self.get_file(txt).strip(), Schedule(self.get_file(html)).__str__().encode("utf-8").strip())

    def test_parse_schedule(self):
        self._equal("raum5710.txt", "raum1171.html")
        #self._equal("raum5710_2.txt", "raum5710_2.html")

if __name__ == '__main__':
    unittest.main()
