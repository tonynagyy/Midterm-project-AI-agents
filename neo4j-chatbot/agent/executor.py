import logging
from neo4j import GraphDatabase
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jExecutor:
    def __init__(self):
        try:
            self.driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise ConnectionError(
                f"Cannot connect to Neo4j at {NEO4J_URI}. "
                "Check that Neo4j is running and credentials are correct."
            ) from e

    def close(self):
        try:
            self.driver.close()
        except Exception:
            pass

    def execute_query(self, query: str) -> list:
        """Executes a Cypher query and returns results as a list of dicts."""
        logger.debug(f"Executing Cypher:\n{query}")
        try:
            with self.driver.session() as session:
                result = session.run(query)
                records = [record.data() for record in result]
                logger.debug(f"Query returned {len(records)} record(s).")
                return records
        except Exception as e:
            logger.error(f"Error executing query:\n{query}\nError: {e}")
            raise
