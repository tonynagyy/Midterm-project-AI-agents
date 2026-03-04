from neo4j import GraphDatabase
import logging
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Neo4jExecutor:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        self.driver.close()

    def execute_query(self, query: str):
        """Executes a Cypher query against the Neo4j database and returns the results."""
        try:
            with self.driver.session() as session:
                result = session.run(query)
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Error executing query:\\n{query}\\nError: {e}")
            raise
