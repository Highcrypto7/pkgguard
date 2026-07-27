"""Multilingual license-restriction detection.

Every language ships as a *pair* of tests: a restrictive phrasing that must be
caught, and a permissive phrasing in the same language that must not be. The
second half is the important one — flagging MIT as non-commercial is worse than
missing a restriction, because it teaches the operator to ignore ⚠️.
"""

import pytest

from pkgguard.checks.license_i18n import search_restrictive, supported_languages

# (language code, restrictive text, permissive text in the same language)
CASES = [
    ("en", "Commercial use is prohibited.", "Commercial use is permitted and encouraged."),
    ("ko", "재판매, 유료 재배포, 유료 서비스 번들링을 금지합니다.", "상업적 이용을 허용합니다. 자유롭게 재판매할 수 있습니다."),
    ("ja", "本ソフトウェアの商用利用は禁止されています。", "商用利用可能です。"),
    ("zh", "禁止商业用途。", "允许商业使用。"),
    ("es", "Prohibido el uso comercial.", "El uso comercial está permitido."),
    ("pt", "Proibido o uso comercial.", "O uso comercial é permitido."),
    ("fr", "Utilisation commerciale interdite.", "Utilisation commerciale autorisée."),
    ("de", "Die kommerzielle Nutzung ist untersagt.", "Die kommerzielle Nutzung ist gestattet."),
    ("it", "Uso commerciale vietato.", "Uso commerciale consentito."),
    ("nl", "Commercieel gebruik is verboden.", "Commercieel gebruik is toegestaan."),
    ("pl", "Zabronione użycie komercyjne.", "Użycie komercyjne jest dozwolone."),
    ("ru", "Коммерческое использование запрещено.", "Коммерческое использование разрешено."),
    ("uk", "Комерційне використання заборонено.", "Комерційне використання дозволено."),
    ("tr", "Ticari kullanım yasaktır.", "Ticari kullanıma izin verilir."),
    ("id", "Dilarang untuk penggunaan komersial.", "Penggunaan komersial diperbolehkan."),
    ("vi", "Cấm sử dụng cho mục đích thương mại.", "Cho phép sử dụng thương mại."),
    ("th", "ห้ามใช้เพื่อการค้า", "อนุญาตให้ใช้เพื่อการค้า"),
    ("ar", "يحظر الاستخدام التجاري", "الاستخدام التجاري مسموح"),
    ("hi", "व्यावसायिक उपयोग निषिद्ध है", "व्यावसायिक उपयोग की अनुमति है"),
    ("sv", "Kommersiell användning är förbjuden.", "Kommersiell användning är tillåten."),
    ("cs", "Komerční použití je zakázáno.", "Komerční použití je povoleno."),
    ("ro", "Utilizarea comercială este interzisă.", "Utilizarea comercială este permisă."),
    ("el", "Απαγορεύεται η εμπορική χρήση.", "Επιτρέπεται η εμπορική χρήση."),
    ("he", "שימוש מסחרי אסור", "שימוש מסחרי מותר"),
]


@pytest.mark.parametrize("lang,restrictive,_permissive", CASES)
def test_restriction_detected(lang, restrictive, _permissive):
    hit = search_restrictive(restrictive)
    assert hit is not None, f"[{lang}] missed restriction: {restrictive!r}"


@pytest.mark.parametrize("lang,_restrictive,permissive", CASES)
def test_permissive_not_flagged(lang, _restrictive, permissive):
    """The dangerous direction: never call an allowing license restrictive."""
    hit = search_restrictive(permissive)
    assert hit is None, (
        f"[{lang}] false positive on permissive text {permissive!r} "
        f"-> {hit.kind}: {hit.snippet!r}"
    )


# Verbatim openings of the licenses pkgguard sees most often. A regression here
# would mislabel a large share of the ecosystem.
REAL_PERMISSIVE = [
    ("MIT", "MIT License\n\nCopyright (c) 2026 Example\n\nPermission is hereby granted, "
            "free of charge, to any person obtaining a copy of this software and associated "
            "documentation files (the \"Software\"), to deal in the Software without "
            "restriction, including without limitation the rights to use, copy, modify, "
            "merge, publish, distribute, sublicense, and/or sell copies of the Software"),
    ("Apache-2.0", "Apache License\nVersion 2.0, January 2004\n"
                   "Licensed under the Apache License, Version 2.0 (the \"License\"); "
                   "you may not use this file except in compliance with the License."),
    ("BSD-3", "Redistribution and use in source and binary forms, with or without "
              "modification, are permitted provided that the following conditions are met."),
    ("ISC", "Permission to use, copy, modify, and/or distribute this software for any "
            "purpose with or without fee is hereby granted."),
]


@pytest.mark.parametrize("name,text", REAL_PERMISSIVE)
def test_standard_permissive_licenses_clean(name, text):
    hit = search_restrictive(text)
    assert hit is None, f"{name} misread as restrictive -> {hit.kind}: {hit.snippet!r}"


@pytest.mark.parametrize("text,expect_lang", [
    ("Commercial use requires a separate license.", "en"),
    ("상업적 이용은 별도의 라이선스가 필요합니다.", "ko"),
    ("商用利用は別途ライセンスが必要です。", "ja"),
    ("El uso comercial requiere una licencia separada.", "es"),
    ("Die kommerzielle Nutzung erfordert eine separate Lizenz.", "de"),
])
def test_gated_commercial_use_is_a_restriction(text, expect_lang):
    """"Requires a separate licence" answers "can I ship this for free?" with no.

    Legally a gate rather than a ban, but identical in consequence for the
    question pkgguard exists to answer. This family was missed before v0.2.0.
    """
    hit = search_restrictive(text)
    assert hit is not None, f"missed gated commercial use: {text!r}"
    assert hit.language == expect_lang


def test_language_is_reported():
    """The finding names the language, which explains the NOASSERTION."""
    hit = search_restrictive("재판매를 금지합니다")
    assert hit is not None and hit.language == "ko"


def test_empty_and_none_safe():
    assert search_restrictive("") is None
    assert search_restrictive("   \n  ") is None
    assert search_restrictive(None) is None


def test_supported_languages_is_broad():
    langs = supported_languages()
    assert len(langs) >= 20, f"expected broad coverage, got {len(langs)}"
    # The scripts most likely to be hand-written and mis-classified by GitHub.
    for critical in ("ko", "ja", "zh", "ru", "ar", "hi", "th"):
        assert critical in langs, f"{critical} missing from supported languages"


def test_unrelated_prose_not_flagged():
    """Two unrelated sentences must not pair across a long gap."""
    text = ("This library is used commercially by many teams. " + "x" * 300 +
            " Redistribution of the trademark is prohibited.")
    assert search_restrictive(text) is None
