"""PlaybookRetriever — orchestrates RAG retrieval from diagnosed_gaps and recommendations."""

from __future__ import annotations

from src.rag.retrieval import ChunkIndex, build_default_index
from src.rag.schemas import PlaybookRetrievalResult, RetrievalQuery


class PlaybookRetriever:
    """Orchestrates retrieval of NVIDIA playbook context for a set of diagnosed gaps."""

    def __init__(self, index: ChunkIndex | None = None) -> None:
        self.index = index if index is not None else build_default_index()

    def retrieve_for_gaps(
        self,
        diagnosed_gaps: list[dict],
        nvidia_technology_candidates: list[dict],
        recommendations: list[dict],
        top_k_per_query: int = 2,
    ) -> list[PlaybookRetrievalResult]:
        """Retrieve context for each unique gap + technology combination.

        Parameters
        ----------
        diagnosed_gaps:
            List of gap dicts (from GapDiagnosisResult.diagnosed_gaps).
        nvidia_technology_candidates:
            List of tech candidate dicts (from nvidia_technology_candidates).
        recommendations:
            List of recommendation dicts (from RecommendationResult.recommendations).

        Returns
        -------
        list[PlaybookRetrievalResult]
            One result per gap + technology combination.
        """
        results: list[PlaybookRetrievalResult] = []

        tech_by_gap: dict[str, set[str]] = {}
        for gap in diagnosed_gaps:
            gap_val = gap.get("gap", "")
            if isinstance(gap_val, str) and gap.get("detected", False):
                tech_by_gap.setdefault(gap_val, set())

        for tc in nvidia_technology_candidates:
            gap_val = tc.get("addresses_gap", "")
            tech_name = tc.get("technology_name", "")
            if isinstance(gap_val, str) and isinstance(tech_name, str):
                if gap_val in tech_by_gap:
                    tech_by_gap[gap_val].add(tech_name)

        for gap_val, techs in tech_by_gap.items():
            if not techs:
                query = RetrievalQuery(gap_type=gap_val)
                contexts = self.index.retrieve(query, top_k=top_k_per_query)
                results.append(
                    PlaybookRetrievalResult(
                        query=query,
                        contexts=contexts,
                        total_found=len(contexts),
                        missing_context=len(contexts) == 0,
                        reasoning=f"No technologies mapped for gap '{gap_val}'",
                    )
                )
            else:
                for tech in sorted(techs):
                    query = RetrievalQuery(gap_type=gap_val, technology=tech)
                    contexts = self.index.retrieve(query, top_k=top_k_per_query)
                    results.append(
                        PlaybookRetrievalResult(
                            query=query,
                            contexts=contexts,
                            total_found=len(contexts),
                            missing_context=len(contexts) == 0,
                            reasoning=(f"Retrieved context for gap '{gap_val}' with technology '{tech}'"),
                        )
                    )

        return results

    def retrieve_for_brief(
        self,
        diagnosed_gaps: list[dict],
        nvidia_technology_candidates: list[dict],
        recommendations: list[dict],
    ) -> list[dict]:
        """Returns a simplified list of dicts suitable for brief embedding.

        The brief continues to function normally even if this returns empty.
        """
        results = self.retrieve_for_gaps(diagnosed_gaps, nvidia_technology_candidates, recommendations)
        return [r.model_dump() for r in results]
