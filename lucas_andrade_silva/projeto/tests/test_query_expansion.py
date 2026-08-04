import unittest

from rag.retrieval.query_expansion import (
    is_likely_portuguese,
    parse_expansions,
)


class QueryExpansionTests(unittest.TestCase):
    def test_detects_portuguese_query(self):
        self.assertTrue(
            is_likely_portuguese("Quais serviços da NVIDIA servem para inferência?")
        )
        self.assertTrue(
            is_likely_portuguese(
                "Compare DGX Cloud, NVIDIA NIM e Omniverse Cloud"
            )
        )
        self.assertFalse(is_likely_portuguese("Which NVIDIA services support inference?"))

    def test_parses_numbered_expansions_and_removes_duplicates(self):
        content = """
        1. NVIDIA inference services
        2. NVIDIA inference deployment solutions
        3. NVIDIA inference services
        """

        self.assertEqual(
            parse_expansions(content, "serviços NVIDIA para inferência"),
            [
                "NVIDIA inference services",
                "NVIDIA inference deployment solutions",
            ],
        )


if __name__ == "__main__":
    unittest.main()
