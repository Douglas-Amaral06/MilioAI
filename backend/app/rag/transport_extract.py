"""Strict extractor for the reviewed two-page VT table; aborts on schema/count changes."""

import hashlib
import re

from pypdf import PdfReader

DOMAIN = "beneficios.vale_transporte.segunda_via"
EXPECTED_CODES = {
    "10398",
    "10420",
    "164",
    "15515",
    "15566",
    "15510",
    "15511",
    "15512",
    "15780",
    "15779",
    "7099",
    "216",
    "2337",
    "5631",
    "182",
    "15508",
    "10771",
    "10394",
    "15504",
    "15506",
    "3854",
    "3845",
    "1071",
    "1892",
    "503",
    "89",
    "9156",
    "738",
    "472",
    "155",
    "200",
    "937",
    "15723",
}
FIELDS = [
    ("uf", "UF"),
    ("code", "Código do benefício"),
    ("name", "Cartão / operadora"),
    ("requester", "Quem solicita"),
    ("payer", "Quem paga"),
    ("payment", "Forma de pagamento"),
    ("fee", "Taxa"),
    ("procedure", "Procedimento integral"),
    ("review", "Pendências de revisão"),
]


def extract_rows(path):
    reader = PdfReader(path)
    if len(reader.pages) != 2:
        raise ValueError("Expected the reviewed two-page table")
    records = []
    for number, page in enumerate(reader.pages, 1):
        text = re.sub(r"Page \d+\s*$", "", page.extract_text()).strip()
        for match in re.finditer(r"(?m)^SP\s+(\d+)\s+([\s\S]*?)(?=^SP\s+\d+\s+|\Z)", text):
            code, raw = match.groups()
            parsed = re.match(
                r"(.+?)\s+(Jovem|Empresa)\s+(Jovem|Empresa)\s+(.+?)\s+(De R\$ \d+,\d+ a R\$ \d+,\d+|\d+ [Tt]arifas|\d+,\d+ R\$)\s+([\s\S]+)",
                raw,
            )
            if not parsed:
                raise ValueError(f"Cannot safely parse benefit {code}")
            name, requester, payer, payment, fee, procedure = parsed.groups()
            if fee.endswith(" R$"):
                fee = "R$ " + fee[:-3].strip()
            review = []
            if code == "3854":
                review.append(
                    "Divergência no PDF: coluna Taxa informa 6 tarifas; procedimento menciona taxa de 21,30. Confirmar com a operadora, sem converter ou escolher um dos valores."
                )
            if code == "503":
                review.append(
                    "A coluna Quem solicita informa Jovem, mas o procedimento permite qualquer pessoa. Confirmar a condição aplicável."
                )
            if code == "15779":
                review.append(
                    "O procedimento menciona endereço abaixo, mas nenhum endereço é informado nesta linha."
                )
            if code == "9156":
                review.append(
                    "O procedimento menciona página de autoatendimento e WhatsApp, mas não informa URL nem número."
                )
            if code == "155":
                review.append(
                    "O procedimento menciona um telefone 0800 sem informar o número completo. A faixa na coluna é De R$ 11,8 a R$ 47,20; os valores por via constam no procedimento."
                )
            records.append(
                dict(
                    code=code,
                    uf="SP",
                    name=name.strip(),
                    requester=requester,
                    payer=payer,
                    payment=payment.strip(),
                    fee=fee,
                    procedure=re.sub(r"\s+", " ", procedure).strip(),
                    page=number,
                    review=" ".join(review),
                )
            )
    codes = [row["code"] for row in records]
    if len(records) != 33 or len(set(codes)) != 33 or set(codes) != EXPECTED_CODES:
        raise ValueError("Expected exactly the 33 reviewed benefit codes")
    return records


def record_text(row):
    return "\n".join(f"{label}: {row[key]}" for key, label in FIELDS if row.get(key))


def record_hash(row):
    return hashlib.sha256(record_text(row).encode()).hexdigest()
