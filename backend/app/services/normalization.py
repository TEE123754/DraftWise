import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.domain.models import PARTIES, PORTS, FieldName


@dataclass(frozen=True)
class Normalized:
    value: str | int | None
    rule: str
    reason: str | None = None


PORT_LOCODES: dict[str, str] = {
    # Singapore
    "singapore": "SGSIN",
    "sgsin": "SGSIN",
    "port of singapore": "SGSIN",
    # China
    "nantong": "CNNTG",
    "cnntg": "CNNTG",
    "shanghai": "CNSHA",
    "cnsha": "CNSHA",
    "rugao": "CNSHA",
    "rugao nantong shanghai": "CNSHA",
    # Malaysia
    "port klang": "MYPKG",
    "mypkg": "MYPKG",
    "port kelang": "MYPKG",
    "port klang westport": "MYPKG",
    "westport port klang": "MYPKG",
    "west port": "MYPKG",
    "westport": "MYPKG",
    # India
    "nhava sheva": "INNSA",
    "innsa": "INNSA",
    "jawaharlal nehru": "INNSA",
    "tuticorin": "INTUT",
    "intut": "INTUT",
    "v o chidambaranar": "INTUT",
    "voc port": "INTUT",
    "chennai": "INMAA",
    "inmaa": "INMAA",
    # Indonesia
    "buatan": "IDBUA",
    "idbua": "IDBUA",
    "jakarta": "IDJKT",
    "tanjung priok": "IDTPP",
    # UAE
    "jebel ali": "AEJEA",
    "aejea": "AEJEA",
    "jebel ali port": "AEJEA",
    "jebel ali dubai": "AEJEA",
    "dubai": "AEJEA",
    # Kenya
    "mombasa": "KEMBA",
    "kemba": "KEMBA",
    "kilindini": "KEMBA",
    # Lithuania
    "klaipeda": "LTKLJ",
    "ltklj": "LTKLJ",
    # US
    "houston": "USHOU",
    "ushou": "USHOU",
    "port of houston": "USHOU",
    "new york": "USNYC",
    "usnyc": "USNYC",
    "long beach": "USLGB",
    "uslgb": "USLGB",
    "savannah": "USSAV",
    "ussav": "USSAV",
    "baltimore": "USBAL",
    "usbal": "USBAL",
    # Vietnam
    "hochiminh city": "VNSGN",
    "ho chi minh city": "VNSGN",
    "ho chi minh": "VNSGN",
    "vnsgn": "VNSGN",
    "saigon": "VNSGN",
    # South Korea
    "pyeongtaek": "KRPTK",
    "krptk": "KRPTK",
    "busan": "KRPUS",
    "krpus": "KRPUS",
    "pusan": "KRPUS",
    # Slovenia
    "koper": "SIKOP",
    "sikop": "SIKOP",
    # Poland
    "gdansk": "PLGDN",
    "plgdn": "PLGDN",
    # Turkey
    "mersin": "TRMER",
    "trmer": "TRMER",
    # Israel
    "ashdod": "ILASH",
    "ilash": "ILASH",
    # Nigeria
    "apapa": "NGAPP",
    "ngapp": "NGAPP",
    "lagos": "NGLOS",
    # Guinea
    "conakry": "GNCKY",
    "gncky": "GNCKY",
    # Chile
    "valparaiso": "CLVAP",
    "clvap": "CLVAP",
    # Peru
    "callao": "PECLL",
    "pecll": "PECLL",
    "port of callao": "PECLL",
    # Australia
    "fremantle": "AUFRE",
    "aufre": "AUFRE",
    "brisbane": "AUBNE",
    "aubne": "AUBNE",
    # Myanmar
    "yangon": "MMRGN",
    "mmrgn": "MMRGN",
    "rangoon": "MMRGN",
    # Pakistan
    "karachi": "PKKHI",
    "pkkhi": "PKKHI",
    # Jordan
    "aqaba": "JOAQB",
    "joaqb": "JOAQB",
    # Philippines
    "cebu": "PHCEB",
    "phceb": "PHCEB",
}


_TRAILING_LOCODE = re.compile(r"\(\s*[A-Za-z]{2}[A-Za-z0-9]{3}\s*\)")


def port_locode(value: str) -> Normalized:
    # A printed name and its trailing "(UN/LOCODE)" can disagree, e.g. "SINGAPORE (MYPKG)". The
    # name is what a reader sees, so a recognised name governs and a stale code cannot hide a change.
    if _TRAILING_LOCODE.search(value):
        by_name = _resolve_port(text_key(_TRAILING_LOCODE.sub(" ", value)))
        if by_name:
            return Normalized(by_name, "port_locode_canonical_v1")
    key = text_key(value)
    if not key:
        return Normalized(None, "port_unresolved_v1", "No usable port identity")
    code = _resolve_port(key)
    if code:
        return Normalized(code, "port_locode_canonical_v1")
    # A port outside the alias table is identified by its name alone: "Colombo, Sri Lanka",
    # "COLOMBO (LKCMB)" and "Colombo" are one port, so the country and code suffixes are dropped.
    return Normalized(text_key(re.split(r"[,(]", value, maxsplit=1)[0]) or key, "identity_exact_v1")


def _resolve_port(key: str) -> str | None:
    if not key:
        return None
    if key in PORT_LOCODES:
        return PORT_LOCODES[key]
    # Strip common port noise words
    cleaned = re.sub(r"\b(port of|port|cy|cfs|terminal|harbour|harbor)\b", " ", key)
    # Strip country names
    cleaned = re.sub(
        r"\b(peru|uae|united arab emirates|china|kenya|india|indonesia|malaysia|singapore|vietnam|south korea|korea|slovenia|poland|turkey|turkiye|israel|nigeria|guinea|chile|australia|myanmar|pakistan|jordan|philippines|us|usa|united states)\b",
        " ",
        cleaned,
    )
    cleaned = " ".join(cleaned.split())
    if cleaned in PORT_LOCODES:
        return PORT_LOCODES[cleaned]
    for alias, code in PORT_LOCODES.items():
        if len(alias) >= 4 and (alias == cleaned or alias in key):
            return code
    return None


def party(value: str) -> Normalized:
    cleaned = unicodedata.normalize("NFKC", value).strip()
    # The name is the first line, or the first " | " segment when a spreadsheet joins the
    # address to the name on one line.
    lines = [part.strip() for part in re.split(r"\n|\s\|\s", cleaned) if part.strip()]
    if not lines:
        return Normalized(None, "party_unresolved_v1", "Empty party name")
    name = lines[0]
    name = re.sub(
        r"^(?:(?:m/s|messrs|to the order of|consignee|shipper|notify party|c/o)\s*[:.-]?\s*)+",
        "",
        name,
        flags=re.I,
    ).strip()
    key = text_key(name)
    key = re.sub(r"\blimited\b", "ltd", key)
    key = re.sub(r"\bincorporated\b", "inc", key)
    key = re.sub(r"\bcorporation\b", "corp", key)
    key = re.sub(r"\bcompany\b", "co", key)
    key = " ".join(key.split())
    if not key:
        return Normalized(None, "party_unresolved_v1", "No usable party identity")
    return Normalized(key, "party_normalized_v1")


def text_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def parse_decimal(value: str) -> Decimal | None:
    value = value.strip().replace("\u00a0", " ")
    if not re.fullmatch(r"\d+(?:[., ]\d+)*", value) or len(value) > 40:
        return None
    if " " in value:
        if not re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?", value):
            return None
        value = value.replace(" ", "")
    if "," in value and "." in value:
        # Both separators establish the format only with valid grouping.
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+", value):
            value = value.replace(",", "")
        elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", value):
            value = value.replace(".", "").replace(",", ".")
        else:
            return None
    elif "," in value:
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", value):
            value = value.replace(",", "")
        elif re.fullmatch(r"\d+,\d{1,2}", value):
            value = value.replace(",", ".")
        else:
            return None
    elif value.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


_WEIGHT = r"\s*([\d.,\s]+)\s*(kg|kgs|kilograms?|mt|metric\s+tonnes?|tonnes?|lb|lbs|pounds?)\s*"


def _label_unit(context: str) -> str | None:
    """The single weight unit named by a field's quoted label, e.g. 'Gross Weight (KGS)'."""
    found = {
        "kg" if re.match(r"kg|kilo", unit, re.I) else unit.lower()
        for unit in re.findall(r"\b(kgs?|kilograms?|mt|tonnes?|lbs?)\b", context, re.I)
    }
    return next(iter(found)) if len(found) == 1 else None


def weight(value: str, context: str = "", counterpart: str = "") -> Normalized:
    text = unicodedata.normalize("NFKC", value)
    match = re.fullmatch(_WEIGHT, text, re.I)
    assumed = False
    if not match and re.fullmatch(r"\s*[\d.,\s]+\s*", text):
        # A bare number takes the unit its own label states, then the one the other document
        # states. With neither, it is read in the field's defined unit (kilograms), and the rule
        # name records that assumption.
        unit = _label_unit(context) or _label_unit(counterpart)
        assumed = unit is None
        match = re.fullmatch(_WEIGHT, f"{text} {unit or 'kg'}", re.I)
    if not match or (number := parse_decimal(match[1])) is None or number <= 0:
        return Normalized(
            None,
            "weight_unresolved_v1",
            "Weight requires an unambiguous positive numeric value",
        )
    if assumed and number < 1000:
        # 22 could as easily be tonnes as kilograms: assume kg only where it is plausibly kg.
        return Normalized(None, "weight_unresolved_v1", "A small bare weight may be in tonnes")
    unit = match[2].lower()
    multiplier = (
        Decimal("0.45359237")
        if unit.startswith(("lb", "pound"))
        else (Decimal(1000) if unit.startswith(("mt", "metric", "tonne")) else Decimal(1))
    )
    normalized = format(number * multiplier, "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return Normalized(normalized, "decimal_unit_assumed_kg_v1" if assumed else "decimal_unit_exact_v1")


def containers(value: str) -> Normalized:
    value = (
        unicodedata.normalize("NFKC", value).strip().casefold().replace("'", "").replace("’", "")
    )
    if re.fullmatch(r"\d{1,6}(?:\s*(?:containers?|cntrs?))?", value):
        count = int(re.match(r"\d+", value)[0])
    elif re.fullmatch(
        r"\d{1,6}\s*[x×]\s*(?:20|40|45)\s*(?:hc|gp|hq|dv|fcl|reefer)(?:\s*\+\s*\d{1,6}\s*[x×]\s*(?:20|40|45)\s*(?:hc|gp|hq|dv|fcl|reefer))*",
        value,
    ):
        count = sum(int(n) for n in re.findall(r"(\d+)\s*[x×]", value))
    else:
        return Normalized(
            None,
            "count_unresolved_v1",
            "Container quantity is not explicit; packages and TEU are not counts",
        )
    if count <= 0:
        return Normalized(None, "count_unresolved_v1", "Container count must be positive")
    return Normalized(count, "integer_exact_v1")


def normalize(
    field: FieldName, value: str, context: str = "", counterpart: str = ""
) -> Normalized:
    """`context` is the quoted text around the value (its label) and `counterpart` the other
    document's value and label; both are used only to find a weight's unit."""
    if field == FieldName.WEIGHT:
        return weight(value, context, counterpart)
    if field == FieldName.CONTAINERS:
        return containers(value)
    if field in PORTS:
        return port_locode(value)
    if field in PARTIES:
        return party(value)
    key = text_key(value)
    if not key:
        return Normalized(None, "text_unresolved_v1", "No usable identity")
    return Normalized(key, "identity_exact_v1")
