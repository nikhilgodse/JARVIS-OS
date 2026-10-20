"""Tests for WhatsApp messaging skill."""

import unittest
from jarvis.skills import whatsapp


class TestWhatsAppIntent(unittest.TestCase):
    """Test WhatsApp intent detection."""

    def test_whatsapp_explicit(self):
        result = whatsapp.detect_intent("open whatsapp")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_OPEN)

    def test_message_with_whatsapp(self):
        result = whatsapp.detect_intent("send Rahul on whatsapp")
        self.assertIsNotNone(result)
        self.assertIn("whatsapp", result["intent"])

    def test_message_without_whatsapp(self):
        result = whatsapp.detect_intent("send Rahul hello")
        self.assertIsNotNone(result)
        self.assertIn("whatsapp", result["intent"])

    def test_not_whatsapp(self):
        result = whatsapp.detect_intent("hello")
        self.assertIsNone(result)

    def test_web_search_not_whatsapp(self):
        result = whatsapp.detect_intent("search google for WhatsApp")
        self.assertIsNone(result)

    def test_find_on_whatsapp(self):
        result = whatsapp.detect_intent("find Shreyash on WhatsApp")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEARCH)


class TestWhatsAppParsing(unittest.TestCase):
    """Test recipient and message extraction."""

    def test_send_with_message(self):
        r, m = whatsapp._parse_command("send Rahul hello")
        self.assertEqual(r, "Rahul")
        self.assertEqual(m, "hello")

    def test_message_with_that(self):
        r, m = whatsapp._parse_command("message Mom that I'll be late")
        self.assertEqual(r, "Mom")
        self.assertEqual(m, "I'll be late")

    def test_tell_with_message(self):
        r, m = whatsapp._parse_command("tell Rahul I'm coming home")
        self.assertEqual(r, "Rahul")
        self.assertEqual(m, "I'm coming home")

    def test_send_quoted_message(self):
        r, m = whatsapp._parse_command("send Rahul 'where are you?'")
        self.assertEqual(r, "Rahul")
        self.assertEqual(m, "where are you?")

    def test_message_no_message(self):
        r, m = whatsapp._parse_command("send Rahul")
        self.assertEqual(r, "Rahul")
        self.assertEqual(m, "")

    def test_open_chat(self):
        r, m = whatsapp._parse_command("open Rahul's WhatsApp chat")
        self.assertEqual(r, "Rahul")
        self.assertEqual(m, "")

    def test_clean_name(self):
        self.assertEqual(whatsapp._clean_name("Rahul's"), "Rahul")
        self.assertEqual(whatsapp._clean_name("the Mom"), "Mom")
        self.assertEqual(whatsapp._clean_name("Rahul."), "Rahul")

    def test_send_to_pattern(self):
        r, m = whatsapp._parse_command("send Hi message to Shreyash")
        self.assertEqual(r, "Shreyash")
        self.assertEqual(m, "Hi message")


class TestWhatsAppHandler(unittest.TestCase):
    """Test the skill handler function."""

    def test_handler_returns_none_for_non_whatsapp(self):
        result = whatsapp.handler("hello world", {})
        self.assertIsNone(result)

    def test_handler_returns_none_for_random_text(self):
        result = whatsapp.handler("what is the weather", {})
        self.assertIsNone(result)

    def test_handler_no_recipient(self):
        result = whatsapp.handler("send on whatsapp", {})
        self.assertIn("Who would you like to message", result)


if __name__ == "__main__":
    unittest.main()
