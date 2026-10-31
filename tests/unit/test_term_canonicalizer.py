from astrbot_plugin_self_learning.services.jargon.term_canonicalizer import (
    TermCanonicalizer,
)


def test_canonicalizer_alias_and_noise_normalization():
    canonicalizer = TermCanonicalizer(alias_map={"yyds": "永远的神"})
    result = canonicalizer.canonicalize("  “这个YYDS啊”  ")

    assert result.surface == "“这个YYDS啊”"
    assert result.canonical_term == "永远的神"
    assert 0.2 <= result.confidence <= 1.0
    assert "alias_map" in result.normalization_reason


def test_canonicalizer_empty_input():
    canonicalizer = TermCanonicalizer()
    result = canonicalizer.canonicalize("")

    assert result.canonical_term == ""
    assert result.confidence == 0.0
    assert result.normalization_reason == "empty"
