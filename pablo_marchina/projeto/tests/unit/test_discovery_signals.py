from __future__ import annotations

from src.discovery.signals import calculate_confidence, detect_ai_native_signals


class TestDetectAiNativeSignals:
    def test_detects_llm_keyword(self) -> None:
        result = detect_ai_native_signals(
            "We build LLM-powered solutions for Brazilian enterprises",
            source_url="https://example.com",
            source_id="test",
        )
        assert result["signal_count"] >= 1
        assert any(s["signal"] == "LLM" or "llm" in s["signal"].lower() for s in result["signals"])
        assert result["confidence_contribution"] > 0

    def test_detects_multiple_signals(self) -> None:
        result = detect_ai_native_signals(
            "GPU-accelerated inference with TensorRT and CUDA for LLM training",
            source_url="https://example.com",
            source_id="test",
        )
        assert result["signal_count"] >= 4
        assert result["confidence_contribution"] >= 0.4

    def test_no_signals(self) -> None:
        result = detect_ai_native_signals(
            "We make handmade wooden furniture",
            source_url="https://example.com",
            source_id="test",
        )
        assert result["signal_count"] == 0
        assert result["confidence_contribution"] == 0.0

    def test_detects_portuguese_ia_keyword(self) -> None:
        result = detect_ai_native_signals(
            "startup brasileira de inteligencia artificial focada em NLP",
            source_url="https://example.com",
            source_id="test",
        )
        assert result["signal_count"] >= 2
        assert result["confidence_contribution"] >= 0.2

    def test_detects_nvidia_tech(self) -> None:
        result = detect_ai_native_signals(
            "plataforma otimizada com TensorRT e CUDA para inferencia em GPU",
            source_url="https://example.com",
            source_id="test",
        )
        assert result["signal_count"] >= 3
        assert result["has_nvidia_tech"] is True

    def test_evidence_excerpts_generated(self) -> None:
        result = detect_ai_native_signals(
            "Our machine learning platform runs on RAPIDS for data science",
            source_url="https://example.com/tech",
            source_id="test",
        )
        assert len(result["evidence_excerpts"]) > 0
        excerpt = result["evidence_excerpts"][0]
        assert "source_url" in excerpt
        assert "excerpt" in excerpt
        assert "signal" in excerpt


class TestCalculateConfidence:
    def test_high_confidence_manual_seed(self) -> None:
        conf = calculate_confidence(
            has_name=True,
            has_website=True,
            signal_contribution=0.6,
            is_manual_seed=True,
            source_reliable=True,
        )
        assert isinstance(conf, float)
        assert conf >= 0.7

    def test_high_confidence_name_and_signals(self) -> None:
        conf = calculate_confidence(
            has_name=True,
            has_website=False,
            signal_contribution=0.4,
        )
        assert isinstance(conf, float)
        assert conf >= 0.7

    def test_low_confidence_no_name_no_signals(self) -> None:
        conf = calculate_confidence(
            has_name=False,
            has_website=False,
            signal_contribution=0.0,
        )
        assert isinstance(conf, float)
        assert conf <= 0.1

    def test_high_from_signals_alone(self) -> None:
        conf = calculate_confidence(
            has_name=False,
            has_website=False,
            signal_contribution=0.9,
        )
        assert isinstance(conf, float)
        assert conf >= 0.7

    def test_confidence_bounds(self) -> None:
        for contrib in [0.0, 0.1, 0.3, 0.5, 0.7, 1.0]:
            conf = calculate_confidence(
                has_name=False,
                has_website=False,
                signal_contribution=contrib,
            )
            assert 0.0 <= conf <= 1.0
