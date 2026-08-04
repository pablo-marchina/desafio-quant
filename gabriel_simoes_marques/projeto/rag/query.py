from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge


async def query_nvidia_techs(queries: list[str], graphiti: Graphiti, num_results: int = 5) -> list[EntityEdge]:
    seen = set()
    results = []

    for query in queries:
        edges = await graphiti.search(query, num_results=num_results)
        for edge in edges:
            if edge.uuid not in seen:
                seen.add(edge.uuid)
                results.append(edge)

    return results
