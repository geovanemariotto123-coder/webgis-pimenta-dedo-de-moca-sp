#!/usr/bin/env python3
import html
import json
import re
import subprocess
import tempfile
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PRICES_FILE = ROOT / "prices.json"
CEAGESP_URL = "https://ceagesp.gov.br/cotacoes/"
CEASA_URL = "https://ceasacampinas.com.br/cotacoes-anteriores"
HEADERS = {"User-Agent": "GeoTerra-WebGIS/1.0 (+https://github.com/geovanemariotto123-coder)"}


def fetch(url, data=None):
    body = urlencode(data).encode() if data else None
    request = Request(url, data=body, headers=HEADERS)
    with urlopen(request, timeout=90) as response:
        return response.read()


def normalize(value):
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value.upper()).strip()


def number(value):
    cleaned = re.sub(r"[^0-9,.-]", "", value)
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    return float(cleaned)


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell, self.in_cell = [], [], [], False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.in_cell, self.cell = True, []

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell:
            self.row.append(" ".join(self.cell).strip())
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)


def update_ceagesp():
    landing = fetch(CEAGESP_URL).decode("utf-8", "replace")
    match = re.search(r"var Grupos = (\{.*?\});", landing, re.S)
    if not match:
        raise RuntimeError("Lista de datas da CEAGESP não encontrada")
    groups = json.loads(match.group(1))
    dates = groups.get("LEGUMES") or []
    if not dates:
        raise RuntimeError("Sem cotações de legumes na CEAGESP")
    latest = max(dates, key=lambda d: datetime.strptime(d, "%d/%m/%Y"))
    result = fetch(CEAGESP_URL, {"cot_grupo": "LEGUMES", "cot_data": latest}).decode("utf-8", "replace")
    parser = TableParser()
    parser.feed(result)
    for row in parser.rows:
        if row and "PIMENTA DEDO DE MOCA" in normalize(row[0]):
            unit_index = next((i for i, cell in enumerate(row) if normalize(cell) == "KG"), None)
            if unit_index is None or len(row) < unit_index + 4:
                continue
            return {
                "product": "Pimenta dedo-de-moça",
                "date": latest,
                "unit": "kg",
                "low": number(row[unit_index + 1]),
                "common": number(row[unit_index + 2]),
                "high": number(row[unit_index + 3]),
                "source_url": CEAGESP_URL,
                "status": "ok",
            }
    raise RuntimeError("Pimenta dedo-de-moça não encontrada na cotação da CEAGESP")


def latest_ceasa_pdf():
    page = html.unescape(fetch(CEASA_URL).decode("utf-8", "replace"))
    pattern = re.compile(r'href="([^"]+\.pdf)"[^>]*>\s*<time[^>]*>(\d{2}/\d{2}/\d{4})', re.I)
    links = [(datetime.strptime(date, "%d/%m/%Y"), urljoin(CEASA_URL, href), date) for href, date in pattern.findall(page)]
    if not links:
        raise RuntimeError("PDFs da CEASA Campinas não encontrados")
    return max(links, key=lambda item: item[0])[1:]


def update_ceasa():
    pdf_url, date = latest_ceasa_pdf()
    pdf = fetch(pdf_url)
    available_languages = subprocess.run(["tesseract", "--list-langs"], check=True, capture_output=True, text=True).stdout
    ocr_language = "por" if "por" in available_languages.split() else "eng"
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        pdf_path = folder / "cotacao.pdf"
        pdf_path.write_bytes(pdf)
        prefix = folder / "page"
        subprocess.run(["pdftoppm", "-png", "-r", "180", str(pdf_path), str(prefix)], check=True, stdout=subprocess.DEVNULL)
        lines = []
        for image_path in sorted(folder.glob("page-*.png")):
            result = subprocess.run(["tesseract", str(image_path), "stdout", "-l", ocr_language], check=True, capture_output=True, text=True)
            lines.extend(result.stdout.splitlines())
    candidates = []
    for line in lines:
        normalized = normalize(line)
        if "PIMENTA" not in normalized or not any(name in normalized for name in ("ARDIDA", "VERMELHA")):
            continue
        values = re.findall(r"\d+[.,]\d+", line)
        if len(values) >= 3:
            candidates.append(("Pimenta ardida/vermelha", [number(v) for v in values[-3:]]))
    if not candidates:
        raise RuntimeError("Pimenta ardida/vermelha não encontrada por OCR no boletim da CEASA Campinas")
    product, values = candidates[0]
    return {
        "product": product,
        "date": date,
        "unit": "kg",
        "low": values[0],
        "common": values[1],
        "high": values[2],
        "source_url": pdf_url,
        "status": "ok",
    }


def main():
    previous = json.loads(PRICES_FILE.read_text(encoding="utf-8")) if PRICES_FILE.exists() else {"sources": {}}
    sources = previous.setdefault("sources", {})
    history = previous.setdefault("history", {})
    errors = []
    for key, updater in (("ceagesp", update_ceagesp), ("ceasa_campinas", update_ceasa)):
        try:
            result = updater()
            sources[key] = result
            series = history.setdefault(key, [])
            point = {
                field: result[field]
                for field in ("date", "low", "common", "high")
                if field in result
            }
            series = [item for item in series if item.get("date") != result.get("date")]
            series.append(point)
            series.sort(key=lambda item: datetime.strptime(item["date"], "%d/%m/%Y"))
            history[key] = series[-2500:]
        except Exception as exc:
            errors.append(f"{key}: {exc}")
            sources.setdefault(key, {})["status"] = "erro na atualização; mantido último valor válido"
    now = datetime.now(ZoneInfo("America/Sao_Paulo"))
    previous["updated_at"] = now.isoformat(timespec="seconds")
    previous["updated_at_display"] = now.strftime("%d/%m/%Y às %H:%M")
    previous["errors"] = errors
    PRICES_FILE.write_text(json.dumps(previous, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if errors:
        print("Avisos:", *errors, sep="\n- ")


if __name__ == "__main__":
    main()
