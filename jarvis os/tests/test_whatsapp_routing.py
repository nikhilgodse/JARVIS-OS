"""Tests for WhatsApp intent routing in the Router."""

import unittest
from jarvis.skills import whatsapp


class TestWhatsAppRouting(unittest.TestCase):
    """Test that WhatsApp commands are correctly routed."""

    def test_open_whatsapp(self):
        result = whatsapp.detect_intent("Open WhatsApp.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_OPEN)

    def test_open_whatsapp_web(self):
        result = whatsapp.detect_intent("Open WhatsApp Web.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_OPEN)

    def test_send_message_with_recipient(self):
        result = whatsapp.detect_intent("Send Hi to Shreyash on WhatsApp.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEND)
        self.assertIn("shreyash", result["recipient"].lower())
        self.assertEqual(result["message"], "Hi")

    def test_message_with_saying(self):
        result = whatsapp.detect_intent("Message Shreyash on WhatsApp saying I'll call you later.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEND)
        self.assertIn("shreyash", result["recipient"].lower())

    def test_find_chat(self):
        result = whatsapp.detect_intent("Find Shreyash on WhatsApp.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEARCH)
        self.assertIn("shreyash", result["recipient"].lower())

    def test_web_search_google(self):
        result = whatsapp.detect_intent("Search Google for WhatsApp.")
        self.assertIsNone(result)

    def test_web_search_the_web(self):
        result = whatsapp.detect_intent("Search the web for WhatsApp.")
        self.assertIsNone(result)

    def test_open_and_send(self):
        result = whatsapp.detect_intent("Open WhatsApp and send Hi message to Shreyash.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEND)
        self.assertIn("shreyash", result["recipient"].lower())

    def test_web_search_for_person(self):
        result = whatsapp.detect_intent("Search Google for Shreyash.")
        self.assertIsNone(result)

    def test_send_whatsapp_message(self):
        result = whatsapp.detect_intent("Send a WhatsApp message to Rahul.")
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], whatsapp.INTENT_WHATSAPP_SEND)
        self.assertIn("rahul", result["recipient"].lower())


if __name__ == "__main__":
    unittest.main()
