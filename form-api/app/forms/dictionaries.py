"""Map normalized dropdown labels to COI dictionary names."""

_COUNTRY_DICTIONARY = dict.fromkeys(
    ("kraj", "kraj urodzenia", "kraj zamieszkania", "państwo pobytu", "państwo zamieszkania"),
    "Kraje",
)

SELECT_DICTIONARIES = {**_COUNTRY_DICTIONARY}
