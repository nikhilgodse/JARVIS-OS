import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.skills import weather


class TestWeather(unittest.TestCase):
    def test_no_place_returns_guidance(self):
        reply = weather.handler('what is the weather', {})
        self.assertIn('Which city?', reply)

    def test_place_extracted(self):
        with mock.patch.object(weather, '_geocode', return_value=(35.6895, 139.6917, 'Tokyo')):
            with mock.patch.object(weather, '_forecast', return_value={
                'current': {'temperature_2m': 22.5, 'weather_code': 0, 'apparent_temperature': 23.0},
                'daily': {'temperature_2m_max': [25.0], 'temperature_2m_min': [18.0]}
            }):
                reply = weather.handler('weather in Tokyo', {})
                self.assertIn('Tokyo', reply)
                self.assertIn('22.5', reply)

    def test_unknown_place(self):
        with mock.patch.object(weather, '_geocode', return_value=None):
            reply = weather.handler('weather in UnknownCityXYZ', {})
            self.assertIn('couldn\'t find', reply)

    def test_unrelated_text_returns_none(self):
        self.assertIsNone(weather.handler('hello world', {}))


if __name__ == '__main__':
    unittest.main()
