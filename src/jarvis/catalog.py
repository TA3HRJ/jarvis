"""Komut kataloğu: her niyet için Katman 1 regex kalıpları ve Katman 2/3 için örnek ifadeler."""

from dataclasses import dataclass, field
import re


@dataclass
class Intent:
    name: str
    regex_patterns: list[str]
    example_phrases: list[str]
    slots: list[str] = field(default_factory=list)
    _compiled: list[re.Pattern] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.regex_patterns]

    def match_regex(self, text: str) -> dict | None:
        for pattern in self._compiled:
            m = pattern.match(text.strip())
            if m:
                return m.groupdict()
        return None


CATALOG: list[Intent] = [
    Intent(
        name="saat_kac",
        regex_patterns=[r"^saat kaç\??$", r"^saat kaçta\??$"],
        example_phrases=["saat kaç", "şu an saat kaç", "saati söyler misin"],
    ),
    Intent(
        name="ekrani_kilitle",
        regex_patterns=[r"^ekranı kilitle$", r"^kilitle$"],
        example_phrases=["ekranı kilitle", "bilgisayarı kilitler misin", "ekran kilidini aç... hayır kilitle"],
    ),
    Intent(
        name="ses_ayarla",
        regex_patterns=[r"^sesi (?P<seviye>\d{1,3}) ?(a|e|ya|ye)? ?ayarla$", r"^ses seviyesini (?P<seviye>\d{1,3}) yap$"],
        example_phrases=["sesi 50'ye ayarla", "ses seviyesini 30 yap", "sesi yüzde yetmişe getir"],
        slots=["seviye"],
    ),
    Intent(
        name="sesi_kis",
        regex_patterns=[r"^sesi kıs$", r"^sesi azalt$"],
        example_phrases=["sesi kıs", "sesi biraz azaltır mısın", "çok yüksek sesi düşür"],
    ),
    Intent(
        name="sesi_ac",
        regex_patterns=[r"^sesi aç$", r"^sesi artır$"],
        example_phrases=["sesi aç", "sesi biraz artırır mısın", "sesi yükselt"],
    ),
    Intent(
        name="hava_durumu",
        regex_patterns=[r"^(?P<sehir>[\wçğıöşü]+)'?(d[ae]|de|da) hava nasıl\??$", r"^bugün hava nasıl\??$"],
        example_phrases=["bugün hava nasıl", "İstanbul'da hava nasıl", "dışarısı sıcak mı"],
        slots=["sehir"],
    ),
    Intent(
        name="alarm_kur",
        regex_patterns=[r"^(?P<saat>\d{1,2}[:.]\d{2}) için alarm kur$", r"^alarm kur (?P<saat>\d{1,2}[:.]\d{2})$"],
        example_phrases=["yarın sabah yediye alarm kur", "07:30 için alarm kur", "bir saat sonra beni uyar"],
        slots=["saat"],
    ),
]


def find_intent(name: str) -> Intent | None:
    return next((i for i in CATALOG if i.name == name), None)
