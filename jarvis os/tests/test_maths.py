import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import maths


class TestMaths(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(maths.handler('what is 2 + 2', {}), '4')
        self.assertEqual(maths.handler('calculate (10 + 5) * 2', {}), '30')
        self.assertEqual(maths.handler('compute 2^3', {}), '8')

    def test_percentage(self):
        self.assertEqual(maths.handler('15% of 200', {}), '15% of 200 = 30')

    def test_unit_conversion(self):
        r = maths.handler('convert 10 miles to km', {})
        self.assertIsNotNone(r)
        self.assertIn('km', r)

    def test_temp_conversion(self):
        r = maths.handler('convert 0 celsius to fahrenheit', {})
        self.assertEqual(r, '0C = 32F')

    def test_invalid_syntax_safe(self):
        self.assertIsNone(maths.handler('what is foo + bar', {}))
        self.assertIsNone(maths.handler('hello there', {}))


if __name__ == '__main__':
    unittest.main()
