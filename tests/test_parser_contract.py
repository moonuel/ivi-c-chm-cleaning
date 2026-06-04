from __future__ import annotations

from pathlib import Path

from ivi_chm.parser import parse_document


def test_parse_document_contract(mini_html_dir: Path) -> None:
    record = parse_document(mini_html_dir / "Mini_NormalizedAlias.html")

    assert record.symbol == "Mini_NormalizedAlias"
    assert record.path_id == "Mini_NormalizedAlias"
    assert record.source_path.endswith("Mini_NormalizedAlias.html")
    assert record.keywords == ["Mini_NormalizedAlias", "Mini_NormalizedAlias function"]
    assert "MiniNormalizedAlias" in record.aliases
    assert record.summary == "A helper for normalized alias retrieval tests."
    assert record.abstract == "Returns the normalized alias test record."
    assert record.prototype.startswith("ViStatus Mini_NormalizedAlias(")
    assert len(record.parameters) == 1
    assert record.parameters[0].name == "Vi"
    assert record.see_also[0]["text"] == "Mini_FulltextAlpha"
