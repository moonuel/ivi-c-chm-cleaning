from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
import re

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ParameterDoc:
    name: str
    description: str


@dataclass(slots=True)
class DocRecord:
    symbol: str
    kind: str
    path_id: str
    title: str
    summary: str
    abstract: str
    prototype: str
    keywords: list[str]
    function_tree_node: str
    aliases: list[str]
    parameters: list[ParameterDoc]
    returns: str
    remarks: str
    commands: str
    requirements: str
    defined_values: list[dict[str, str]]
    see_also: list[dict[str, str]]
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["parameters"] = [asdict(param) for param in self.parameters]
        return data


def _clean(text: str) -> str:
    return " ".join(text.split())


def _text(node) -> str:
    return _clean(node.get_text(" ", strip=True)) if node else ""


def _section_text(section_id: str, soup: BeautifulSoup) -> str:
    section = soup.select_one(f"div#{section_id}")
    if not section:
        return ""
    return _clean(section.get_text(" ", strip=True))


def _normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _page_path_id(path: Path) -> str:
    return path.stem


def _extract_keywords(soup: BeautifulSoup) -> list[str]:
    keywords: list[str] = []
    for tag in soup.select("mshelp\\:keyword"):
        term = _clean(tag.get("term", ""))
        if term and term not in keywords:
            keywords.append(term)
    return keywords


def _extract_abstract(soup: BeautifulSoup) -> str:
    for tag in soup.select("mshelp\\:attr[name='Abstract']"):
        value = _clean(tag.get("value", ""))
        if value:
            return value
    return ""


def _extract_tree_node(soup: BeautifulSoup, kind: str) -> str:
    label = "Function Tree Node:" if kind == "function" else "Attribute Tree Node:"
    marker = soup.find(string=lambda text: isinstance(text, str) and label in text)
    if not marker:
        return ""
    parent = marker.parent
    if not parent:
        return ""
    text = _clean(parent.get_text(" ", strip=True))
    return text.split(label, 1)[-1].strip() if label in text else ""


def _extract_aliases(symbol: str, keywords: list[str]) -> list[str]:
    aliases: list[str] = []
    base = symbol.replace("KtNA_", "", 1)
    candidates = [base, symbol, base.replace("_", "")]
    for keyword in keywords:
        if keyword.endswith(" function") or keyword.endswith(" attribute"):
            candidates.append(keyword.rsplit(" ", 1)[0])
    for candidate in candidates:
        normalized = candidate.strip()
        for alias in (normalized, _normalize_identifier(normalized)):
            if alias and alias != symbol and alias not in aliases:
                aliases.append(alias)
    return aliases


def parse_document(path: str | Path) -> DocRecord:
    path = Path(path)
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")

    title = _text(soup.title)
    symbol = title.replace(" Function", "").replace(" Attribute", "").strip()
    kind = "attribute" if symbol.upper().startswith("KTNA_ATTR_") else "function"
    path_id = _page_path_id(path)

    summary = _text(soup.select_one("div.summary"))
    abstract = _extract_abstract(soup)
    keywords = _extract_keywords(soup)
    function_tree_node = _extract_tree_node(soup, kind)

    syntax = soup.select_one("div#syntaxSection")
    prototype = ""
    if syntax:
        pre = syntax.select_one("pre")
        prototype = _text(pre)

    parameters: list[ParameterDoc] = []
    for block in soup.select("dl[paramname]"):
        name = _clean(block.get("paramname", ""))
        desc = _text(block.select_one("dd"))
        if name:
            parameters.append(ParameterDoc(name=name, description=desc))

    returns = ""
    return_heading = soup.find(lambda tag: tag.name == "h4" and _text(tag) == "Return Value")
    if return_heading:
        p = return_heading.find_next("p")
        returns = _text(p)

    remarks = _section_text("remarksSection", soup)
    commands = _section_text("commandsSection", soup)
    requirements = _section_text("requirementsSection", soup)

    defined_values: list[dict[str, str]] = []
    defined_table = soup.select_one("div#defValParamStandardTypeTableSection table")
    if defined_table:
        for row in defined_table.select("tr[data]"):
            cells = [ _text(cell) for cell in row.find_all("td") ]
            if len(cells) == 3:
                defined_values.append({"name": cells[0], "value": cells[1], "description": cells[2]})

    see_also: list[dict[str, str]] = []
    for link in soup.select("div#seeAlsoSection a[href$='.html']"):
        text = _text(link)
        href = link.get("href", "")
        if text and href:
            see_also.append({"text": text, "href": href})

    if not symbol:
        symbol = path.stem

    aliases = _extract_aliases(symbol, keywords)

    return DocRecord(
        symbol=symbol,
        kind=kind,
        path_id=path_id,
        title=title,
        summary=summary,
        abstract=abstract,
        prototype=prototype,
        keywords=keywords,
        function_tree_node=function_tree_node,
        aliases=aliases,
        parameters=parameters,
        returns=returns,
        remarks=remarks,
        commands=commands,
        requirements=requirements,
        defined_values=defined_values,
        see_also=see_also,
        source_path=str(path),
    )
