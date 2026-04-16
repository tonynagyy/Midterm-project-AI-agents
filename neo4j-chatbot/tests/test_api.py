import unittest

from fastapi.testclient import TestClient

from api import app, get_orchestrator


class StubOrchestrator:
    def run_turn(self, user_input: str, thread_id: str = "default"):
        if user_input == "explode":
            raise RuntimeError("boom")

        return {
            "response": "Bukayo Saka plays for Arsenal.",
            "intent": "inquire",
            "latency_ms": 12.5,
            "memory_turns": 2,
            "long_memory_hits": 1,
            "error": "",
        }

    def peek_long_memory(self, thread_id: str, limit: int = 10):
        return [
            {
                "thread_id": thread_id,
                "user_text": "hello",
                "assistant_text": "hi",
                "intent": "chitchat",
                "created_at": 123.0,
            }
        ][:limit]

    def close(self):
        return None


class APITests(unittest.TestCase):
    def setUp(self):
        self.stub = StubOrchestrator()
        app.dependency_overrides[get_orchestrator] = lambda: self.stub
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_agent_chat_success(self):
        payload = {"message": "who plays for arsenal?", "thread_id": "api-test"}
        response = self.client.post("/agent/chat", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], "inquire")
        self.assertEqual(body["memory_turns"], 2)
        self.assertEqual(body["long_memory_hits"], 1)
        self.assertIn("Arsenal", body["response"])

    def test_agent_chat_validation(self):
        response = self.client.post("/agent/chat", json={"message": "", "thread_id": "api-test"})
        self.assertEqual(response.status_code, 422)

    def test_agent_chat_error_path(self):
        response = self.client.post(
            "/agent/chat",
            json={"message": "explode", "thread_id": "api-test"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["detail"], "Agent execution failed.")

    def test_memory_endpoint(self):
        response = self.client.get("/agent/memory/api-test?limit=5")
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["thread_id"], "api-test")
        self.assertEqual(body["count"], 1)
        self.assertEqual(len(body["entries"]), 1)


if __name__ == "__main__":
    unittest.main()
