from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


@dataclass(slots=True)
class ParameterDoc:
    name: str
    description: str


@dataclass(slots=True)
class DocRecord:
    symbol: str
    kind: str
    title: str
    summary: str
    prototype: str
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


def parse_document(path: str | Path) -> DocRecord:
    path = Path(path)
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")

    title = _text(soup.title)
    symbol = title.replace(" Function", "").replace(" Attribute", "").strip()
    kind = "attribute" if symbol.upper().startswith("KTNA_ATTR_") else "function"

    summary = _text(soup.select_one("div.summary"))

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

    return DocRecord(
        symbol=symbol,
        kind=kind,
        title=title,
        summary=summary,
        prototype=prototype,
        parameters=parameters,
        returns=returns,
        remarks=remarks,
        commands=commands,
        requirements=requirements,
        defined_values=defined_values,
        see_also=see_also,
        source_path=str(path),
    )
