import unittest

import agent.cypher_generator as cypher_module


class _CaptureLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []

    def generate(self, prompt: str, max_tokens: int | None = None, model: str | None = None) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "model": model,
            }
        )
        return self.response_text


class CypherModelOverrideTests(unittest.TestCase):
    def setUp(self):
        self._original_model_override = cypher_module.LLM_MODEL_CYPHER

    def tearDown(self):
        cypher_module.LLM_MODEL_CYPHER = self._original_model_override

    def test_uses_cypher_model_override_when_configured(self):
        cypher_module.LLM_MODEL_CYPHER = "qwen2-5-coder-0-5b-neo4j-text2cypher-2024v1"
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)

        llm = _CaptureLLM(
            "MATCH (a:Node)-[r]->(b:Node)\nRETURN type(r) AS relation, b.name AS value\nLIMIT 1"
        )
        generator.llm = llm

        generator.generate(
            user_input="Find transfer information",
            intent="inquire",
            retries=0,
        )

        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(
            llm.calls[0]["model"],
            "qwen2-5-coder-0-5b-neo4j-text2cypher-2024v1",
        )

    def test_falls_back_to_default_model_when_override_missing(self):
        cypher_module.LLM_MODEL_CYPHER = ""
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)

        llm = _CaptureLLM(
            "MATCH (a:Node)-[r]->(b:Node)\nRETURN type(r) AS relation, b.name AS value\nLIMIT 1"
        )
        generator.llm = llm

        generator.generate(
            user_input="Find transfer information",
            intent="inquire",
            retries=0,
        )

        self.assertEqual(len(llm.calls), 1)
        self.assertIsNone(llm.calls[0]["model"])


if __name__ == "__main__":
    unittest.main()
