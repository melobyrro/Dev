"""
Brazilian Portuguese Bible books dictionary with common variants
66 books of the Bible with abbreviations and alternative names
"""

# Full mapping of Bible books with PT-BR variants
BIBLE_BOOKS_PT = {
    # Old Testament
    "Gênesis": ["Genesis", "Gênesis", "Gn", "Ge", "Gen"],
    "Êxodo": ["Êxodo", "Exodo", "Éxodo", "Ex", "Êx"],
    "Levítico": ["Levítico", "Levitico", "Lv", "Lev"],
    "Números": ["Números", "Numeros", "Nm", "Núm", "Num"],
    "Deuteronômio": ["Deuteronômio", "Deuteronomio", "Dt", "Deut"],
    "Josué": ["Josué", "Josue", "Js", "Jos"],
    "Juízes": ["Juízes", "Juizes", "Jz", "Jui", "Juiz"],
    "Rute": ["Rute", "Rt", "Ru"],
    "1 Samuel": ["1 Samuel", "1Samuel", "1 Sm", "1Sm", "I Samuel", "I Sm"],
    "2 Samuel": ["2 Samuel", "2Samuel", "2 Sm", "2Sm", "II Samuel", "II Sm"],
    "1 Reis": ["1 Reis", "1Reis", "1 Rs", "1Rs", "I Reis", "I Rs"],
    "2 Reis": ["2 Reis", "2Reis", "2 Rs", "2Rs", "II Reis", "II Rs"],
    "1 Crônicas": ["1 Crônicas", "1Crônicas", "1 Cr", "1Cr", "I Crônicas", "I Cr"],
    "2 Crônicas": ["2 Crônicas", "2Crônicas", "2 Cr", "2Cr", "II Crônicas", "II Cr"],
    "Esdras": ["Esdras", "Ed", "Esd"],
    "Neemias": ["Neemias", "Ne", "Nee"],
    "Ester": ["Ester", "Et", "Est"],
    "Jó": ["Jó", "Jo", "Job"],
    "Salmos": ["Salmos", "Salmo", "Sl", "Sal", "Ps"],
    "Provérbios": ["Provérbios", "Proverbios", "Pv", "Pr", "Prov"],
    "Eclesiastes": ["Eclesiastes", "Ec", "Ecl"],
    "Cantares": ["Cantares", "Cânticos", "Canticos", "Ct", "Cant", "Cantar dos Cantares"],
    "Isaías": ["Isaías", "Isaias", "Is", "Isa"],
    "Jeremias": ["Jeremias", "Jr", "Jer"],
    "Lamentações": ["Lamentações", "Lamentacões", "Lamentacoes", "Lm", "Lam"],
    "Ezequiel": ["Ezequiel", "Ez", "Eze"],
    "Daniel": ["Daniel", "Dn", "Dan"],
    "Oséias": ["Oséias", "Oseias", "Os", "Ose"],
    "Joel": ["Joel", "Jl", "Joe"],
    "Amós": ["Amós", "Amos", "Am"],
    "Obadias": ["Obadias", "Ob", "Obd"],
    "Jonas": ["Jonas", "Jn", "Jon"],
    "Miquéias": ["Miquéias", "Miqueias", "Mq", "Miq"],
    "Naum": ["Naum", "Na"],
    "Habacuque": ["Habacuque", "Hc", "Hab"],
    "Sofonias": ["Sofonias", "Sf", "Sof"],
    "Ageu": ["Ageu", "Ag"],
    "Zacarias": ["Zacarias", "Zc", "Zac"],
    "Malaquias": ["Malaquias", "Ml", "Mal"],

    # New Testament
    "Mateus": ["Mateus", "Mt", "Mat"],
    "Marcos": ["Marcos", "Mc", "Mar"],
    "Lucas": ["Lucas", "Lc", "Luc"],
    "João": ["João", "Joao", "Jo", "Jn", "Joa"],
    "Atos": ["Atos", "Atos dos Apóstolos", "At"],
    "Romanos": ["Romanos", "Rm", "Rom"],
    "1 Coríntios": ["1 Coríntios", "1Coríntios", "1 Co", "1Co", "I Coríntios", "I Co"],
    "2 Coríntios": ["2 Coríntios", "2Coríntios", "2 Co", "2Co", "II Coríntios", "II Co"],
    "Gálatas": ["Gálatas", "Galatas", "Gl", "Gal"],
    "Efésios": ["Efésios", "Efesios", "Ef"],
    "Filipenses": ["Filipenses", "Fp", "Fil"],
    "Colossenses": ["Colossenses", "Cl", "Col"],
    "1 Tessalonicenses": ["1 Tessalonicenses", "1Tessalonicenses", "1 Ts", "1Ts", "I Tessalonicenses", "I Ts"],
    "2 Tessalonicenses": ["2 Tessalonicenses", "2Tessalonicenses", "2 Ts", "2Ts", "II Tessalonicenses", "II Ts"],
    "1 Timóteo": ["1 Timóteo", "1Timóteo", "1 Tm", "1Tm", "I Timóteo", "I Tm"],
    "2 Timóteo": ["2 Timóteo", "2Timóteo", "2 Tm", "2Tm", "II Timóteo", "II Tm"],
    "Tito": ["Tito", "Tt"],
    "Filemom": ["Filemom", "Fm", "Fle"],
    "Hebreus": ["Hebreus", "Hb", "Heb"],
    "Tiago": ["Tiago", "Tg"],
    "1 Pedro": ["1 Pedro", "1Pedro", "1 Pe", "1Pe", "I Pedro", "I Pe"],
    "2 Pedro": ["2 Pedro", "2Pedro", "2 Pe", "2Pe", "II Pedro", "II Pe"],
    "1 João": ["1 João", "1João", "1 Jo", "1Jo", "I João", "I Jo"],
    "2 João": ["2 João", "2João", "2 Jo", "2Jo", "II João", "II Jo"],
    "3 João": ["3 João", "3João", "3 Jo", "3Jo", "III João", "III Jo"],
    "Judas": ["Judas", "Jd"],
    "Apocalipse": ["Apocalipse", "Ap", "Apo", "Rv", "Revelação"],
}

# Reverse mapping: variant -> canonical name
VARIANT_TO_CANONICAL = {}
for canonical, variants in BIBLE_BOOKS_PT.items():
    for variant in variants:
        VARIANT_TO_CANONICAL[variant.lower()] = canonical


def get_canonical_book_name(book_str: str) -> str:
    """
    Convert any book variant to canonical name

    Args:
        book_str: Book name or abbreviation (e.g., "Gn", "1 Co", "João")

    Returns:
        Canonical book name or original string if not found
    """
    return VARIANT_TO_CANONICAL.get(book_str.lower(), book_str)


def is_valid_book(book_str: str) -> bool:
    """
    Check if a string is a valid Bible book name/abbreviation

    Args:
        book_str: Potential book name

    Returns:
        True if valid Bible book
    """
    return book_str.lower() in VARIANT_TO_CANONICAL


# List of all canonical book names (in order)
ALL_BOOKS_CANONICAL = list(BIBLE_BOOKS_PT.keys())
