"""Multilingual detection of commercial-use restrictions in license text.

Open source is global; license files are not always in English. A hand-written
``LICENSE`` in Korean, Spanish or Russian is mapped to ``NOASSERTION`` by
GitHub's classifier, so an English-only pattern reads it as "unclassifiable"
and lets it through as ✅ — the single worst outcome for a tool whose job is to
answer "can I use this commercially?".

**Why proximity matching instead of phrase lists.** Word order is the whole
problem. Korean states the prohibited acts first and negates once at the end
("재판매, 유료 재배포, 번들링을 *금지합니다*"). German splits the verb
("Die kommerzielle Nutzung ist *untersagt*"). Turkish and Japanese put the
negation last; Arabic and Hebrew read right-to-left. A list of exact phrases
would need every permutation per language and would still miss real files.

So instead we look for two *concepts* co-occurring inside a short window:

    <commercial-use term>  … within N chars …  <prohibition term>

in **either order**. That one rule covers every word order above, and adding a
language means adding two short vocabulary lists rather than reasoning about
its grammar.

**Guarding against the opposite error.** "Commercial use is permitted" must not
be flagged. Prohibition vocabulary is therefore kept narrow and explicit
(prohibited / forbidden / not allowed / banned), never generic negation, and
every language ships a permissive-phrasing test in ``tests/test_license_i18n.py``.

Detection is intentionally recall-oriented but evidence-backed: a hit is a
``⚠️ WARN`` with the matching snippet quoted, never a hard ❌. A human reads the
quote and decides.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Characters allowed between the two concepts. Generous enough to span a clause
# or a short list, tight enough that two unrelated sentences don't pair up.
_WINDOW = 80


# --- vocabulary -------------------------------------------------------------
# Per language: terms meaning "commercial use" and terms meaning "prohibited".
# Values are regex fragments (already lowercase; matching is case-insensitive).
# Scripts without case (CJK, Thai, Arabic, Hindi) are unaffected by that.

_COMMERCIAL: Dict[str, List[str]] = {
    "en": [r"commercial(?:ly)?", r"for profit", r"profit[- ]making"],
    "ko": [r"상업적?", r"영리", r"상용", r"유료\s*(?:서비스|배포|재배포|번들링)", r"재판매"],
    "ja": [r"商用", r"商業", r"営利", r"転売"],
    "zh": [r"商业", r"商業", r"商用", r"营利", r"營利", r"转售", r"轉售"],
    "es": [r"comercial(?:es|mente)?", r"con fines de lucro"],
    "pt": [r"comercial(?:is|mente)?", r"com fins lucrativos"],
    "fr": [r"commercial(?:e|es|ement)?", r"à but lucratif"],
    "de": [r"kommerziell(?:e|en|er|es)?", r"gewerblich(?:e|en|er|es)?", r"erwerbszweck\w*"],
    "it": [r"commercial(?:e|i|mente)?", r"a scopo di lucro"],
    "nl": [r"commercie(?:el|le)", r"commercieel gebruik"],
    "pl": [r"komercyjn\w+", r"zarobkow\w+"],
    "ru": [r"коммерческ\w*", r"комерційн\w*", r"в коммерческих цел\w*"],
    "uk": [r"комерційн\w*"],
    "tr": [r"ticari", r"ticarî"],
    "id": [r"komersial", r"tujuan komersial"],
    "vi": [r"thương mại"],
    "th": [r"เพื่อการค้า", r"เชิงพาณิชย์", r"ทางการค้า"],
    "ar": [r"التجاري\w*", r"تجاري\w*"],
    "hi": [r"व्यावसायिक", r"वाणिज्यिक"],
    "sv": [r"kommersiell\w*"],
    "cs": [r"komerčn\w+"],
    "ro": [r"comercial\w*"],
    "el": [r"εμπορικ\w*"],
    "he": [r"מסחרי\w*"],
    "fa": [r"تجاری"],
}

# "Prohibited" here also covers *gated* use — "requires a separate licence",
# "contact us for commercial use". Legally that is not a ban, but for the
# question this tool answers ("can I ship this commercially, today, for free?")
# the answer is the same: no. Missing this family let
# "Commercial use requires a separate license" pass as unrestricted.
_PROHIBITION: Dict[str, List[str]] = {
    "en": [r"prohibit\w*", r"forbidden", r"not permitted", r"not allowed",
           r"banned", r"may not", r"disallowed", r"restricted", r"without.{0,20}permission",
           r"requires?\s+(?:a\s+)?(?:separate|paid|commercial|written)",
           r"subject to\s+(?:a\s+)?separate", r"purchase\s+a\s+licen",
           r"contact\s+(?:us|the author)"],
    "ko": [r"별도\s*(?:의\s*)?(?:라이선스|라이센스|계약|협의)", r"문의\s*(?:바랍|요망|주세요)", r"금지", r"불가", r"허용하지\s*않", r"할\s*수\s*없", r"제한"],
    "ja": [r"別途\s*(?:ライセンス|契約|許諾)", r"お問い合わせ", r"禁止", r"禁じ", r"不可", r"できません", r"認めら?れ(?:ま)?せん"],
    "zh": [r"需(?:要)?(?:单独|單獨|另行|商业|商業)(?:授权|授權|许可|許可)", r"请联系|請聯繫", r"禁止", r"不得", r"不可", r"不允许", r"不允許", r"未经许可", r"未經許可"],
    "es": [r"requiere\s+(?:una\s+)?licencia\s+(?:separada|comercial|de pago)", r"prohibid\w+", r"no (?:se )?permit\w+", r"no autorizad\w+", r"vedad\w+"],
    "pt": [r"requer\s+(?:uma\s+)?licença\s+(?:separada|comercial)", r"proibid\w+", r"não (?:é )?permitid\w+", r"vedad\w+", r"não autorizad\w+"],
    "fr": [r"n[eé]cessite\s+une\s+licence\s+(?:s[ée]par[ée]e|commerciale)", r"interdit\w*", r"non autoris\w+", r"n['e ]est pas permis", r"prohib\w+"],
    "de": [r"erfordert\s+eine\s+(?:separate|kommerzielle|gesonderte)\s+lizenz", r"untersagt", r"verboten", r"nicht (?:gestattet|erlaubt|zulässig)", r"unzulässig"],
    "it": [r"vietat\w+", r"non (?:è )?consentit\w+", r"proibit\w+", r"non permess\w+"],
    "nl": [r"verboden", r"niet toegestaan", r"niet toegelaten"],
    "pl": [r"zabronion\w+", r"zakazan\w+", r"niedozwolon\w+", r"bez zgody"],
    "ru": [r"требует\s+отдельн\w+\s+лицензи", r"запрещ\w*", r"не допускается", r"не разрешается", r"без разрешения"],
    "uk": [r"заборонен\w*", r"не дозволя\w*", r"без дозволу"],
    "tr": [r"yasak\w*", r"izin verilmez", r"izinsiz", r"kullanılamaz"],
    "id": [r"dilarang", r"tidak diizinkan", r"tidak diperbolehkan", r"tanpa izin"],
    "vi": [r"cấm", r"không được", r"không cho phép"],
    "th": [r"ห้าม", r"ไม่อนุญาต"],
    "ar": [r"يحظر", r"محظور", r"ممنوع", r"لا يجوز"],
    "hi": [r"निषिद्ध", r"वर्जित", r"मना है", r"अनुमति नहीं"],
    "sv": [r"förbjud\w*", r"inte tillåt\w*"],
    "cs": [r"zakázán\w*", r"není dovolen\w*", r"nesmí"],
    "ro": [r"interzis\w*", r"nu este permis\w*"],
    "el": [r"απαγορεύ\w*", r"δεν επιτρέπεται"],
    "he": [r"אסור", r"נאסר"],
    "fa": [r"ممنوع", r"مجاز نیست"],
}

# Single tokens that already mean "non-commercial" on their own — no second
# concept needed. Kept separate so they can be matched without a window.
_STANDALONE = [
    (r"non[-\s]?commercial", "en"),
    (r"cc[-\s]?by[-\s]?nc", "en"),
    (r"비상업|비영리", "ko"),
    (r"非商用|非営利", "ja"),
    (r"非商业|非商業|非营利|非營利", "zh"),
    (r"no comercial|sin fines de lucro", "es"),
    (r"não comercial|sem fins lucrativos", "pt"),
    (r"non commercial|non[- ]lucratif", "fr"),
    (r"nicht[-\s]?kommerziell", "de"),
    (r"non commerciale|senza scopo di lucro", "it"),
    (r"niet[-\s]?commercieel", "nl"),
    (r"niekomercyjn\w+", "pl"),
    (r"некоммерческ\w*", "ru"),
    (r"некомерційн\w*", "uk"),
    (r"ticari olmayan", "tr"),
    (r"nonkomersial|non[- ]komersial", "id"),
    (r"phi thương mại", "vi"),
    (r"icke[-\s]?kommersiell\w*", "sv"),
    (r"nekomerčn\w+", "cs"),
    (r"necomercial\w*", "ro"),
    (r"μη εμπορικ\w*", "el"),
    (r"לא מסחרי", "he"),
    (r"غير تجاري", "ar"),
    (r"गैर[-\s]?व्यावसायिक", "hi"),
]

# "research / personal / academic use only" — a second independent restriction
# family. Requires the scope word and an "only" word close together.
_SCOPE = {
    "en": ([r"research", r"academic", r"personal", r"evaluation", r"educational"],
           [r"only", r"solely", r"exclusively"]),
    "ko": ([r"연구", r"학술", r"개인적?", r"교육"], [r"목적으로만", r"용도로만", r"만\s*허용", r"에\s*한(?:함|정)"]),
    "ja": ([r"研究", r"個人", r"学術", r"教育"], [r"のみ", r"限[りる]", r"に限"]),
    "zh": ([r"研究", r"个人", r"個人", r"学习", r"學習", r"教育"], [r"仅供", r"僅供", r"仅限", r"僅限", r"only"]),
    "es": ([r"investigación", r"personal", r"académic\w+", r"educativ\w+"], [r"solo|sólo|únicamente|exclusivamente"]),
    "pt": ([r"pesquisa", r"pessoal", r"acadêmic\w+", r"educacional"], [r"apenas|somente|exclusivamente"]),
    "fr": ([r"recherche", r"personnel\w*", r"académique", r"éducatif"], [r"uniquement|seulement|exclusivement"]),
    "de": ([r"forschung\w*", r"privat\w*", r"akademisch\w*", r"bildung\w*"], [r"nur|ausschließlich|lediglich"]),
    "it": ([r"ricerca", r"personale", r"accademic\w+"], [r"solo|soltanto|esclusivamente"]),
    "ru": ([r"исследовательск\w*", r"личн\w*", r"учебн\w*"], [r"только|исключительно"]),
}


@dataclass
class RestrictiveHit:
    """A detected commercial restriction, with enough context to justify it."""

    language: str
    kind: str          # "commercial-prohibition" | "non-commercial" | "scope-only"
    snippet: str
    start: int


def _alt(fragments: List[str]) -> str:
    return "|".join(fragments)


def _compile_pairs() -> List[Tuple[str, re.Pattern]]:
    """One proximity pattern per language, matching either concept order."""
    out = []
    for lang, comm in _COMMERCIAL.items():
        proh = _PROHIBITION.get(lang)
        if not proh:
            continue
        c, p = _alt(comm), _alt(proh)
        pattern = re.compile(
            rf"(?:(?:{c})[\s\S]{{0,{_WINDOW}}}?(?:{p}))"
            rf"|(?:(?:{p})[\s\S]{{0,{_WINDOW}}}?(?:{c}))",
            re.IGNORECASE,
        )
        out.append((lang, pattern))
    return out


def _compile_scope() -> List[Tuple[str, re.Pattern]]:
    out = []
    for lang, (scopes, onlys) in _SCOPE.items():
        s, o = _alt(scopes), _alt(onlys)
        pattern = re.compile(
            rf"(?:(?:{s})[\s\S]{{0,40}}?(?:{o}))|(?:(?:{o})[\s\S]{{0,40}}?(?:{s}))",
            re.IGNORECASE,
        )
        out.append((lang, pattern))
    return out


_PAIR_PATTERNS = _compile_pairs()
_SCOPE_PATTERNS = _compile_scope()
_STANDALONE_PATTERNS = [(re.compile(p, re.IGNORECASE), lang) for p, lang in _STANDALONE]


def _snippet(text: str, start: int, end: int) -> str:
    a = max(0, start - 30)
    return " ".join(text[a:end + 40].split())[:140]


def search_restrictive(text: str) -> Optional[RestrictiveHit]:
    """Return the first commercial restriction found, in any supported language.

    Order matters: an explicit "non-commercial" token is the strongest and
    cheapest signal, so it is tried first; the proximity rules follow.
    """
    if not text or not text.strip():
        return None

    for pattern, lang in _STANDALONE_PATTERNS:
        m = pattern.search(text)
        if m:
            return RestrictiveHit(lang, "non-commercial", _snippet(text, m.start(), m.end()), m.start())

    for lang, pattern in _PAIR_PATTERNS:
        m = pattern.search(text)
        if m:
            return RestrictiveHit(lang, "commercial-prohibition", _snippet(text, m.start(), m.end()), m.start())

    for lang, pattern in _SCOPE_PATTERNS:
        m = pattern.search(text)
        if m:
            return RestrictiveHit(lang, "scope-only", _snippet(text, m.start(), m.end()), m.start())

    return None


def supported_languages() -> List[str]:
    """Language codes with at least commercial+prohibition vocabulary."""
    return sorted({lang for lang, _ in _PAIR_PATTERNS})
