import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.modules import llm


class TestLlm(unittest.TestCase):
    def _clean_env(self):
        """Ensure clean env for each test."""
        for k in ("JARVIS_LLM_API_KEY", "JARVIS_LLM_ENDPOINT", "JARVIS_LLM_MODEL",
                   "NVIDIA_API_KEY", "NVIDIA_BASE_URL", "NVIDIA_MODEL",
                   "AI_PROVIDER", "OLLAMA_ENDPOINT", "OLLAMA_MODEL"):
            os.environ.pop(k, None)

    def test_offline_when_nothing_supplied(self):
        self._clean_env()
        with mock.patch.object(llm.storage, "load", return_value={}):
            llm.reset_router()
            s = llm.settings()
            self.assertIn("localhost", s["endpoint"])

    def test_env_key_configures(self):
        self._clean_env()
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {"JARVIS_LLM_API_KEY": "sk-test"}):
                llm.reset_router()
                self.assertTrue(llm.is_configured())
                s = llm.settings()
                self.assertEqual(s["api_key"], "sk-test")
                self.assertIn("localhost", s["endpoint"])

    def test_env_precedence_over_config(self):
        self._clean_env()
        cfg = {"llm_api_key": "cfg-key", "llm_model": "cfg-model"}
        with mock.patch.object(llm.storage, "load", return_value=cfg):
            with mock.patch.dict(os.environ, {"JARVIS_LLM_MODEL": "env-model"}):
                llm.reset_router()
                s = llm.settings()
                self.assertEqual(s["model"], "env-model")

    def test_guardrail_prepended(self):
        sent = {}

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                import json
                return json.dumps({"choices": [{"message": {"content": "hi"}}]}).encode()

        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {"JARVIS_LLM_ENDPOINT": "http://x/v1",
                                               "JARVIS_LLM_API_KEY": "k",
                                               "AI_PROVIDER": "ollama"}):
                llm.reset_router()
                with mock.patch("urllib.request.urlopen", return_value=FakeResp()) as uo:
                    out = llm.complete([{"role": "user", "content": "hi"}])
        self.assertEqual(out, "hi")
        body = uo.call_args[0][0].data.decode()
        self.assertIn("never claim to have opened", body)


class TestProviderSelection(unittest.TestCase):
    def test_provider_explicit_ollama(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {"AI_PROVIDER": "ollama"}):
                llm.reset_router()
                router = llm._get_router()
                self.assertEqual(router.primary_name, "ollama")

    def test_provider_explicit_nvidia(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {
                "AI_PROVIDER": "nvidia",
                "NVIDIA_API_KEY": "test-key"
            }):
                llm.reset_router()
                router = llm._get_router()
                self.assertEqual(router.primary_name, "nvidia")

    def test_auto_detect_nvidia_key(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {
                "NVIDIA_API_KEY": "test-key",
                "AI_PROVIDER": ""
            }):
                llm.reset_router()
                router = llm._get_router()
                self.assertEqual(router.primary_name, "nvidia")

    def test_auto_detect_no_key(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {
                "NVIDIA_API_KEY": "",
                "AI_PROVIDER": ""
            }):
                llm.reset_router()
                router = llm._get_router()
                self.assertEqual(router.primary_name, "ollama")


class TestFallback(unittest.TestCase):
    def test_fallback_configured(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {
                "AI_PROVIDER": "nvidia",
                "NVIDIA_API_KEY": "test-key",
                "AI_AUTO_FAILOVER": "true"
            }):
                llm.reset_router()
                router = llm._get_router()
                self.assertEqual(router.fallback_name, "ollama")
                self.assertTrue(router.auto_fallback)

    def test_fallback_disabled_by_default(self):
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {
                "AI_PROVIDER": "nvidia",
                "NVIDIA_API_KEY": "test-key",
                "AI_AUTO_FAILOVER": ""
            }):
                llm.reset_router()
                router = llm._get_router()
                self.assertFalse(router.auto_fallback)


class TestHealthCheck(unittest.TestCase):
    def test_ollama_health_check_offline(self):
        provider = llm.OllamaProvider(endpoint="http://localhost:99999/v1/chat/completions")
        health = provider.health_check()
        self.assertEqual(health["status"], "offline")
        self.assertFalse(health["server_reachable"])

    def test_nvidia_health_check_no_key(self):
        provider = llm.NvidiaNimProvider(api_key="")
        health = provider.health_check()
        self.assertEqual(health["status"], "no_api_key")

    def test_nvidia_health_check_auth_error(self):
        def fake_urlopen(req, timeout=None):
            raise llm.urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            provider = llm.NvidiaNimProvider(api_key="bad-key")
            health = provider.health_check()
            self.assertEqual(health["status"], "auth_error")


class TestSecurity(unittest.TestCase):
    def test_doctor_no_key_leak(self):
        """doctor() must never expose API keys."""
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-secret123"}):
                llm.reset_router()
                report = llm.doctor()
                self.assertNotIn("nvapi-secret123", report)

    def test_provider_info_no_key_leak(self):
        """provider_info() must never expose API keys."""
        with mock.patch.object(llm.storage, "load", return_value={}):
            with mock.patch.dict(os.environ, {"NVIDIA_API_KEY": "nvapi-secret456"}):
                llm.reset_router()
                info = llm.provider_info()
                info_str = str(info)
                self.assertNotIn("nvapi-secret456", info_str)


class TestNvidiaProvider(unittest.TestCase):
    def test_complete_requires_key(self):
        provider = llm.NvidiaNimProvider(api_key="")
        with self.assertRaises(RuntimeError) as ctx:
            provider.complete([{"role": "user", "content": "hi"}])
        self.assertIn("API key", str(ctx.exception))

    def test_complete_success(self):
        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                import json
                return json.dumps({"choices": [{"message": {"content": "hello"}}]}).encode()

        provider = llm.NvidiaNimProvider(api_key="test-key")
        with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
            result = provider.complete([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "hello")

    def test_auth_error_message(self):
        def fake_urlopen(req, timeout=None):
            raise llm.urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        provider = llm.NvidiaNimProvider(api_key="bad-key")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                provider.complete([{"role": "user", "content": "hi"}])
            self.assertIn("Authentication failed", str(ctx.exception))


class TestOllamaProvider(unittest.TestCase):
    def test_complete_success(self):
        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                import json
                return json.dumps({"choices": [{"message": {"content": "hi from ollama"}}]}).encode()

        provider = llm.OllamaProvider()
        with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
            result = provider.complete([{"role": "user", "content": "hi"}])
        self.assertEqual(result, "hi from ollama")

    def test_guardrail_prepended(self):
        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self):
                import json
                return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

        provider = llm.OllamaProvider()
        with mock.patch("urllib.request.urlopen", return_value=FakeResp()) as uo:
            provider.complete([{"role": "user", "content": "hi"}])
        body = uo.call_args[0][0].data.decode()
        self.assertIn("never claim to have opened", body)


if __name__ == "__main__":
    unittest.main()
