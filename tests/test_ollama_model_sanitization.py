"""
Unit-Tests für die Validierung und Bereinigung von Ollama-Modellnamen.
Testet alle Konventionen, Sonderzeichen, Groß-/Kleinschreibung, GGUF-Dateinamen,
Namespaces und Tags, um HTTP 400 Fehler vollständig auszuschließen.
"""

import unittest
from src.Install.ollama_model_utils import (
    is_valid_ollama_model_name,
    sanitize_ollama_model_name,
    format_ollama_model_tag
)


class TestOllamaModelSanitization(unittest.TestCase):

    def test_valid_ollama_names(self):
        """Testet Standard-Modellnamen, die bereits valide sind."""
        valid_examples = [
            "llama3.1",
            "llama3.1:8b",
            "deepseek-r1:8b",
            "qwen3:14b",
            "qwen3-coder:30b",
            "codestral",
            "codestral:22b",
            "mistral:latest",
            "thebloke/mistral-7b-instruct:q4_k_m",
            "my_custom_model.v1:tag-1"
        ]
        for name in valid_examples:
            with self.subTest(name=name):
                self.assertTrue(
                    is_valid_ollama_model_name(name),
                    f"'{name}' sollte als valider Ollama-Name erkannt werden."
                )

    def test_invalid_ollama_names(self):
        """Testet ungültige Modellnamen (Großbuchstaben, Sonderzeichen etc.)."""
        invalid_examples = [
            "Codestral",                           # Enthält Großbuchstaben
            "DeepSeek-R1:8B",                      # Enthält Großbuchstaben
            "Mistral-7B-Instruct-v0.2.Q4_K_M.gguf",# Großbuchstaben und .gguf
            "model name with spaces",              # Leerzeichen
            "model(1)[v2]#test",                   # Klammern, Rauten
            "-leading-dash",                       # Führender Bindestrich
            "trailing-dash-",                      # Nachfolgender Bindestrich
            "double--dash",                        # Mehrfache Trennzeichen
            "model:TAG",                           # Großbuchstaben im Tag
            "",                                    # Leerstring
            None                                   # None
        ]
        for name in invalid_examples:
            with self.subTest(name=name):
                self.assertFalse(
                    is_valid_ollama_model_name(name),
                    f"'{name}' sollte als UNGÜLTIG erkannt werden."
                )

    def test_sanitization_converts_uppercase(self):
        """Testet, dass Großbuchstaben zu Kleinbuchstaben konvertiert werden."""
        self.assertEqual(sanitize_ollama_model_name("Codestral"), "codestral")
        self.assertEqual(sanitize_ollama_model_name("DeepSeek-R1:8B"), "deepseek-r1:8b")
        self.assertEqual(sanitize_ollama_model_name("LLaMA-3.1:Latest"), "llama-3.1:latest")
        self.assertEqual(sanitize_ollama_model_name("Qwen-2.5-Coder"), "qwen-2.5-coder")

    def test_sanitization_strips_extensions(self):
        """Testet, dass Dateiendungen (.gguf, .bin, etc.) entfernt werden."""
        self.assertEqual(
            sanitize_ollama_model_name("mistral-7b-instruct.gguf"),
            "mistral-7b-instruct"
        )
        self.assertEqual(
            sanitize_ollama_model_name("DeepSeek-V4-Flash-DSpark-support-0731.gguf"),
            "deepseek-v4-flash-dspark-support-0731"
        )
        self.assertEqual(
            sanitize_ollama_model_name("model.safetensors"),
            "model"
        )
        self.assertEqual(
            sanitize_ollama_model_name("model.bin"),
            "model"
        )

    def test_sanitization_special_characters_and_whitespace(self):
        """Testet das Ersetzen von Sonderzeichen und Leerzeichen."""
        self.assertEqual(
            sanitize_ollama_model_name("model (1) [v2.0] #test!"),
            "model-1-v2.0-test"
        )
        self.assertEqual(
            sanitize_ollama_model_name("my special model & more"),
            "my-special-model-more"
        )

    def test_sanitization_umlauts(self):
        """Testet die Transliteration von Umlauten."""
        self.assertEqual(
            sanitize_ollama_model_name("Größtes-Modell:v1"),
            "groesstes-modell:v1"
        )
        self.assertEqual(
            sanitize_ollama_model_name("über-ki-äöü"),
            "ueber-ki-aeoeue"
        )

    def test_sanitization_edge_cases(self):
        """Testet Edge Cases (leere Strings, nur Sonderzeichen, Doppel-Trennzeichen)."""
        self.assertEqual(sanitize_ollama_model_name(""), "custom-model")
        self.assertEqual(sanitize_ollama_model_name(None), "custom-model")
        self.assertEqual(sanitize_ollama_model_name("!!!@@@###"), "custom-model")
        self.assertEqual(sanitize_ollama_model_name("---___model...name___---"), "model-name")

    def test_format_ollama_model_tag(self):
        """Testet die Hilfsfunktion zur Tag-Generierung aus Dateinamen / Repos."""
        self.assertEqual(
            format_ollama_model_tag("Mistral-7B-Instruct-v0.2.Q4_K_M.gguf"),
            "mistral-7b-instruct-v0.2.q4_k_m"
        )
        self.assertEqual(
            format_ollama_model_tag("C:\\models\\MyModel_v1.0.gguf"),
            "mymodel_v1.0"
        )
        self.assertEqual(
            format_ollama_model_tag("models/deepseek-r1.gguf", custom_tag="custom-tag:latest"),
            "custom-tag:latest"
        )

    def test_all_sanitized_outputs_are_strictly_valid(self):
        """Stellt sicher, dass jedes Ergebnis der Bereinigung 100 % valide ist."""
        test_inputs = [
            "Codestral:22B",
            "DeepSeek-V4-Flash-DSpark-support-0731.gg(…).gguf",
            "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
            "Model@2024#Test!!",
            "---TEST---MODEL---",
            "___test___",
            "äöü_Modell:V1.0",
            "llama3.1:8B",
            "user input with spaces and (brackets)"
        ]
        for raw in test_inputs:
            sanitized = sanitize_ollama_model_name(raw)
            with self.subTest(raw=raw, sanitized=sanitized):
                self.assertTrue(
                    is_valid_ollama_model_name(sanitized),
                    f"Bereinigter Name '{sanitized}' (aus '{raw}') muss is_valid_ollama_model_name() bestehen!"
                )


if __name__ == "__main__":
    unittest.main()
