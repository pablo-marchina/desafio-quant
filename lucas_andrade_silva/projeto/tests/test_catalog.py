import unittest

from rag.catalog import (
    build_url_registry,
    category_names,
    detect_services,
    service_names,
)


class CatalogTests(unittest.TestCase):
    def test_expected_catalog_size(self):
        self.assertEqual(len(service_names()), 53)
        self.assertEqual(len(build_url_registry()), 282)

    def test_shared_url_preserves_all_services(self):
        registry = build_url_registry()
        services = registry["https://www.nvidia.com/en-us/startups/"]["services"]

        self.assertEqual(len(services), 3)

    def test_categories_are_available(self):
        self.assertIn("Software de IA", category_names())

    def test_detects_services_and_aliases_in_query(self):
        detected = detect_services(
            "Compare DGX Cloud, NVIDIA NIM and Omniverse Cloud"
        )

        self.assertEqual(
            detected,
            ["DGX Cloud", "Omniverse Cloud", "NIM Microservices"],
        )


if __name__ == "__main__":
    unittest.main()
