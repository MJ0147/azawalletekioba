"""
Benin Royal Museum catalogue.

Each Oba's name, reign and description are transcribed from the inscription plaque on his
portrait (static/images/museum/<slug>.jpg). Entries are in reign order; eras group them
for the gallery. Oba Akenzua I (c. 1713–1735) has no portrait yet, hence the gap between
Ozuere and Eresoyen.
"""

from __future__ import annotations

from typing import Any

MUSEUM_ERAS: list[dict[str, str]] = [
    {"id": "founding", "title": "Founding of the Eweka Dynasty", "period": "c. 1200–1440"},
    {"id": "warrior-kings", "title": "Warrior Kings and Empire", "period": "1440–1606"},
    {"id": "succession-crisis", "title": "The Succession Crisis", "period": "c. 1606–1713"},
    {"id": "recovery", "title": "Recovery and European Contact", "period": "c. 1735–1888"},
    {"id": "modern", "title": "1897 and the Modern Monarchy", "period": "1888–present"},
]

_INSCRIPTIONS: list[dict[str, str]] = [
    # Founding of the Eweka Dynasty
    {"slug": "oba-eweka-i", "era": "founding", "name": "Oba Eweka I", "reign": "c. 1200–1235",
     "description": "Founded the Eweka dynasty and established the Oba line of Benin"},
    {"slug": "oba-uwakhuahen", "era": "founding", "name": "Oba Uwakhuahen", "reign": "c. 1235–1243",
     "description": "Early consolidation of the Eweka dynasty"},
    {"slug": "oba-ehenmihen", "era": "founding", "name": "Oba Ehenmihen", "reign": "c. 1243–1255",
     "description": "Continued the early Eweka line and royal consolidation"},
    {"slug": "oba-ewedo", "era": "founding", "name": "Oba Ewedo", "reign": "c. 1255–1280",
     "description": "Consolidated royal power, relocated the palace, and introduced major administrative reforms"},
    {"slug": "oba-oguola", "era": "founding", "name": "Oba Oguola", "reign": "c. 1280–1295",
     "description": "Ordered the first major defensive moats around Benin City and advanced brass casting"},
    {"slug": "oba-edoni", "era": "founding", "name": "Oba Edoni", "reign": "c. 1295–1299",
     "description": "Short reign in the early consolidation period"},
    {"slug": "oba-udagbedo", "era": "founding", "name": "Oba Udagbedo", "reign": "c. 1299–1334",
     "description": "Encouraged agriculture and expanded influence toward the Ga region"},
    {"slug": "oba-ohen", "era": "founding", "name": "Oba Ohen", "reign": "c. 1334–1370",
     "description": "Expanded territory and associated with Olokun shrine traditions and guild reforms"},
    {"slug": "oba-egbeka", "era": "founding", "name": "Oba Egbeka", "reign": "c. 1370–1400",
     "description": "Reign marked by political tensions with the Uzama chiefs"},
    {"slug": "oba-orobiru", "era": "founding", "name": "Oba Orobiru", "reign": "c. 1400–1430",
     "description": "Continued pre-imperial rule in a period of limited recorded events"},
    {"slug": "oba-uwaifiokun", "era": "founding", "name": "Oba Uwaifiokun", "reign": "c. 1430–1440",
     "description": "Last pre-imperial Oba; overthrown by Ewuare the Great"},
    # Warrior Kings and Empire
    {"slug": "oba-ewuare-the-great", "era": "warrior-kings", "name": "Oba Ewuare the Great", "reign": "1440–1473",
     "description": "Expanded the empire, fortified Benin City, and established major royal arts and coral regalia traditions"},
    {"slug": "oba-ezoti", "era": "warrior-kings", "name": "Oba Ezoti", "reign": "c. 1473",
     "description": "Reigned only 14 days; assassinated by poisoned arrow at coronation"},
    {"slug": "oba-olua", "era": "warrior-kings", "name": "Oba Olua", "reign": "c. 1473–1480",
     "description": "Son of Ewuare; known for heavy expenditures and links to early Itsekiri leadership"},
    {"slug": "oba-ozolua", "era": "warrior-kings", "name": "Oba Ozolua", "reign": "c. 1480–1504",
     "description": "Warrior king who greatly expanded Benin territory through military campaigns"},
    {"slug": "oba-esigie", "era": "warrior-kings", "name": "Oba Esigie", "reign": "c. 1504–1550",
     "description": "Strengthened Portuguese trade and diplomatic contacts; era of Queen Mother Idia"},
    {"slug": "oba-orhogbua", "era": "warrior-kings", "name": "Oba Orhogbua", "reign": "c. 1550–1578",
     "description": "Portuguese-educated; established Eko (Lagos) military camp and installed the first Oba of Lagos"},
    {"slug": "oba-ehengbuda", "era": "warrior-kings", "name": "Oba Ehengbuda", "reign": "c. 1578–1606",
     "description": "Last great warrior king; expanded territory and fixed the Benin–Oyo boundary at Otun"},
    # The Succession Crisis
    {"slug": "oba-ohuan", "era": "succession-crisis", "name": "Oba Ohuan", "reign": "c. 1606–1641",
     "description": "Defeated rebellious Iyase; died childless, triggering a major succession crisis"},
    {"slug": "oba-ohenzae", "era": "succession-crisis", "name": "Oba Ohenzae", "reign": "c. 1641–1661",
     "description": "Early ruler in the 17th-century succession crisis period"},
    {"slug": "oba-akenzae", "era": "succession-crisis", "name": "Oba Akenzae", "reign": "c. 1661–1669",
     "description": "Short reign during the post-Ohuan succession struggles"},
    {"slug": "oba-akengboi", "era": "succession-crisis", "name": "Oba Akengboi", "reign": "c. 1669–1675",
     "description": "Continued the era of contested succession and reduced royal power"},
    {"slug": "oba-ahenkpaye", "era": "succession-crisis", "name": "Oba Ahenkpaye", "reign": "c. 1675–1684",
     "description": "Ruler during the prolonged 17th-century succession crisis"},
    {"slug": "oba-akengbedo", "era": "succession-crisis", "name": "Oba Akengbedo", "reign": "c. 1684–1689",
     "description": "Continued the era of contested succession and limited royal power"},
    {"slug": "oba-ore-oghene", "era": "succession-crisis", "name": "Oba Ore-Oghene", "reign": "c. 1689–1700",
     "description": "Received papal encouragement; reign in a period of political instability"},
    {"slug": "oba-ewuakpe", "era": "succession-crisis", "name": "Oba Ewuakpe", "reign": "c. 1700–1712",
     "description": "Faced powerful chiefs; struggled to restore monarchical authority"},
    {"slug": "oba-ozuere", "era": "succession-crisis", "name": "Oba Ozuere", "reign": "c. 1712–1713",
     "description": "Short reign as a usurper backed by certain chiefs"},
    # Recovery and European Contact
    {"slug": "oba-eresoyen", "era": "recovery", "name": "Oba Eresoyen", "reign": "c. 1735–1750",
     "description": "Continued recovery of the monarchy; associated with cultural and artistic activity"},
    {"slug": "oba-akengbuda", "era": "recovery", "name": "Oba Akengbuda", "reign": "c. 1750–1804",
     "description": "Long reign of relative stability and consolidation"},
    {"slug": "oba-obanosa", "era": "recovery", "name": "Oba Obanosa", "reign": "c. 1804–1816",
     "description": "Ruled during a period of internal challenges and European contact"},
    {"slug": "oba-ogbebo", "era": "recovery", "name": "Oba Ogbebo", "reign": "1816",
     "description": "Very short reign of approximately eight months"},
    {"slug": "oba-osemwende", "era": "recovery", "name": "Oba Osemwende", "reign": "c. 1816–1848",
     "description": "Long reign with increasing European trade and diplomatic visits"},
    {"slug": "oba-adolo", "era": "recovery", "name": "Oba Adolo", "reign": "c. 1848–1888",
     "description": "Father of Ovonramwen; maintained the kingdom in the decades before the 1897 British expedition"},
    # 1897 and the Modern Monarchy
    {"slug": "oba-ovonramwen-nogbaisi", "era": "modern", "name": "Oba Ovonramwen Nogbaisi", "reign": "1888–1914",
     "description": "Last independent Oba; resisted British invasion and was exiled after the 1897 expedition"},
    {"slug": "oba-eweka-ii", "era": "modern", "name": "Oba Eweka II", "reign": "1914–1933",
     "description": "Restored the Benin monarchy under colonial rule after the interregnum"},
    {"slug": "oba-akenzua-ii", "era": "modern", "name": "Oba Akenzua II", "reign": "1933–1978",
     "description": "Modernized the kingdom and secured return of coral regalia of Ovonramwen"},
    {"slug": "oba-erediauwa", "era": "modern", "name": "Oba Erediauwa", "reign": "1979–2016",
     "description": "Long reign focused on cultural preservation and advocacy for Benin heritage"},
    {"slug": "oba-ewuare-ii", "era": "modern", "name": "Oba Ewuare II", "reign": "2016–present",
     "description": "Leading the global campaign for the return of the Benin Bronzes and cultural revival"},
]

# Catalogue number (reign order) and image URL added for display.
MUSEUM_PORTRAITS: list[dict[str, Any]] = [
    {**entry, "number": number, "image": f"/static/images/museum/{entry['slug']}.jpg"}
    for number, entry in enumerate(_INSCRIPTIONS, start=1)
]


def museum_catalogue() -> list[dict[str, Any]]:
    """Eras in order, each with its portraits."""
    return [
        {**era, "portraits": [p for p in MUSEUM_PORTRAITS if p["era"] == era["id"]]}
        for era in MUSEUM_ERAS
    ]
