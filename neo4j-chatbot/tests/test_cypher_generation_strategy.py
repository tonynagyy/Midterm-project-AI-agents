import unittest

import agent.cypher_generator as cypher_module


class _CaptureLLM:
    def __init__(self, responses):
        if isinstance(responses, str):
            responses = [responses]
        self.responses = list(responses)
        self.calls = []

    def generate(self, prompt: str, max_tokens: int | None = None, model: str | None = None) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "model": model,
            }
        )
        if not self.responses:
            return ""
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


class CypherGenerationStrategyTests(unittest.TestCase):
    def setUp(self):
        self._original_model_override = cypher_module.LLM_MODEL_CYPHER

    def tearDown(self):
        cypher_module.LLM_MODEL_CYPHER = self._original_model_override

    def test_add_intent_uses_deterministic_template_without_llm(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM("MATCH (n) RETURN n")
        generator.llm = llm

        query = generator.generate("Add that Pedri has position Midfielder", "add")

        self.assertIn("MERGE (a:Node {name: 'Pedri'})", query)
        self.assertIn("MERGE (a)-[:HAS_POSITION]->(b)", query)
        self.assertEqual(len(llm.calls), 0)

    def test_update_intent_uses_deterministic_template_without_llm(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM("MATCH (n) RETURN n")
        generator.llm = llm

        query = generator.generate("Update Bukayo Saka team to Arsenal FC", "update")

        self.assertIn("MATCH (a:Node {name: 'Bukayo Saka'})-[r:PLAYS_FOR]->(:Node)", query)
        self.assertIn("MERGE (c:Node {name: 'Arsenal FC'})", query)
        self.assertEqual(len(llm.calls), 0)

    def test_delete_intent_uses_deterministic_template_without_llm(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM("MATCH (n) RETURN n")
        generator.llm = llm

        query = generator.generate("Remove Pedri position fact", "delete")

        self.assertIn("MATCH (a:Node {name: 'Pedri'})-[r:HAS_POSITION]->(:Node)", query)
        self.assertIn("DELETE r", query)
        self.assertEqual(len(llm.calls), 0)

    def test_non_inquire_parse_failure_does_not_fallback_to_llm(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM("MATCH (n) RETURN n")
        generator.llm = llm

        with self.assertRaises(ValueError):
            generator.generate("Update this somehow", "update")

        self.assertEqual(len(llm.calls), 0)

    def test_inquire_repair_trims_semicolon_tail_via_explain(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM(
            "MATCH (a:Node)-[r]->(b:Node) RETURN type(r) AS relation, b.name AS value; extra junk"
        )
        generator.llm = llm

        driver = object()
        generator._ensure_repair_driver = lambda: driver

        def _fake_explain(_driver, query: str):
            if "extra junk" in query:
                return False, "Invalid input"
            return True, ""

        generator._explain_parse = _fake_explain

        query = generator.generate("Find all known relations for Lionel Messi", "inquire", retries=0)

        self.assertEqual(
            query,
            "MATCH (a:Node)-[r]->(b:Node) RETURN type(r) AS relation, b.name AS value",
        )
        self.assertEqual(len(llm.calls), 1)

    def test_inquire_runs_repair_prompt_when_initial_query_invalid(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM(
            [
                "This is not Cypher",
                "MATCH (a:Node)-[r]->(b:Node) RETURN type(r) AS relation, b.name AS value",
            ]
        )
        generator.llm = llm

        driver = object()
        generator._ensure_repair_driver = lambda: driver

        def _fake_explain(_driver, query: str):
            return ("RETURN" in query and "MATCH" in query), "Invalid input"

        generator._explain_parse = _fake_explain

        query = generator.generate("Find all known relations for Lionel Messi", "inquire", retries=0)

        self.assertIn("RETURN type(r) AS relation", query)
        self.assertEqual(len(llm.calls), 2)
        self.assertIn("Fix this Neo4j Cypher query", llm.calls[1]["prompt"])

    def test_inquire_uses_fallback_after_failed_model_and_repair(self):
        generator = cypher_module.CypherGenerator()
        self.addCleanup(generator.close)
        llm = _CaptureLLM(["Not Cypher", "Still not Cypher"])
        generator.llm = llm

        generator._ensure_repair_driver = lambda: None

        query = generator.generate("Find all known relations for Lionel Messi", "inquire", retries=0)

        self.assertIn("MATCH (a:Node)-[r]->(b:Node)", query)
        self.assertIn("RETURN a.name AS source, type(r) AS relation, b.name AS value", query)
        self.assertEqual(len(llm.calls), 2)


if __name__ == "__main__":
    unittest.main()
