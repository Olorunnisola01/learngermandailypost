"""
generate_grammar.py
Generates 5000+ unique German grammar fill-in-the-blank quiz questions (A2-B1):
verb conjugation, pronoun agreement, noun/article gender, adjective endings.
Reuses vocabulary lists from generate_questions.py.
Output: data/grammar.json
"""
import json, random
from pathlib import Path

import generate_questions as gq  # reuses ALL_VERBS / ALL_NOUNS / ALL_ADJECTIVES

random.seed(7)

PERSONS = ["ich", "du", "er", "wir", "ihr", "sie"]
PRONOUN_TEXT = {"ich": "Ich", "du": "Du", "er": "Er", "wir": "Wir", "ihr": "Ihr", "sie": "Sie"}
COMPLEMENTS = ["oft", "manchmal", "jeden Tag", "gern", "heute", "hier", "zusammen", "allein", "immer", "selten"]

# ─── Hardcoded irregular/strong verb present-tense forms ──────────────────────
IRREGULAR = {
    "sein":    {"ich":"bin","du":"bist","er":"ist","wir":"sind","ihr":"seid","sie":"sind"},
    "haben":   {"ich":"habe","du":"hast","er":"hat","wir":"haben","ihr":"habt","sie":"haben"},
    "werden":  {"ich":"werde","du":"wirst","er":"wird","wir":"werden","ihr":"werdet","sie":"werden"},
    "können":  {"ich":"kann","du":"kannst","er":"kann","wir":"können","ihr":"könnt","sie":"können"},
    "müssen":  {"ich":"muss","du":"musst","er":"muss","wir":"müssen","ihr":"müsst","sie":"müssen"},
    "dürfen":  {"ich":"darf","du":"darfst","er":"darf","wir":"dürfen","ihr":"dürft","sie":"dürfen"},
    "sollen":  {"ich":"soll","du":"sollst","er":"soll","wir":"sollen","ihr":"sollt","sie":"sollen"},
    "wollen":  {"ich":"will","du":"willst","er":"will","wir":"wollen","ihr":"wollt","sie":"wollen"},
    "mögen":   {"ich":"mag","du":"magst","er":"mag","wir":"mögen","ihr":"mögt","sie":"mögen"},
    "wissen":  {"ich":"weiß","du":"weißt","er":"weiß","wir":"wissen","ihr":"wisst","sie":"wissen"},
    "fahren":  {"ich":"fahre","du":"fährst","er":"fährt","wir":"fahren","ihr":"fahrt","sie":"fahren"},
    "essen":   {"ich":"esse","du":"isst","er":"isst","wir":"essen","ihr":"esst","sie":"essen"},
    "geben":   {"ich":"gebe","du":"gibst","er":"gibt","wir":"geben","ihr":"gebt","sie":"geben"},
    "lesen":   {"ich":"lese","du":"liest","er":"liest","wir":"lesen","ihr":"lest","sie":"lesen"},
    "sehen":   {"ich":"sehe","du":"siehst","er":"sieht","wir":"sehen","ihr":"seht","sie":"sehen"},
    "sprechen":{"ich":"spreche","du":"sprichst","er":"spricht","wir":"sprechen","ihr":"sprecht","sie":"sprechen"},
    "nehmen":  {"ich":"nehme","du":"nimmst","er":"nimmt","wir":"nehmen","ihr":"nehmt","sie":"nehmen"},
    "helfen":  {"ich":"helfe","du":"hilfst","er":"hilft","wir":"helfen","ihr":"helft","sie":"helfen"},
    "treffen": {"ich":"treffe","du":"triffst","er":"trifft","wir":"treffen","ihr":"trefft","sie":"treffen"},
    "vergessen":{"ich":"vergesse","du":"vergisst","er":"vergisst","wir":"vergessen","ihr":"vergesst","sie":"vergessen"},
    "tragen":  {"ich":"trage","du":"trägst","er":"trägt","wir":"tragen","ihr":"tragt","sie":"tragen"},
    "schlafen":{"ich":"schlafe","du":"schläfst","er":"schläft","wir":"schlafen","ihr":"schlaft","sie":"schlafen"},
    "laufen":  {"ich":"laufe","du":"läufst","er":"läuft","wir":"laufen","ihr":"lauft","sie":"laufen"},
    "halten":  {"ich":"halte","du":"hältst","er":"hält","wir":"halten","ihr":"haltet","sie":"halten"},
    "fallen":  {"ich":"falle","du":"fällst","er":"fällt","wir":"fallen","ihr":"fallt","sie":"fallen"},
    "lassen":  {"ich":"lasse","du":"lässt","er":"lässt","wir":"lassen","ihr":"lasst","sie":"lassen"},
    "waschen": {"ich":"wasche","du":"wäschst","er":"wäscht","wir":"waschen","ihr":"wascht","sie":"waschen"},
    "wachsen": {"ich":"wachse","du":"wächst","er":"wächst","wir":"wachsen","ihr":"wachst","sie":"wachsen"},
    "schlagen":{"ich":"schlage","du":"schlägst","er":"schlägt","wir":"schlagen","ihr":"schlagt","sie":"schlagen"},
    "fangen":  {"ich":"fange","du":"fängst","er":"fängt","wir":"fangen","ihr":"fangt","sie":"fangen"},
    "backen":  {"ich":"backe","du":"bäckst","er":"bäckt","wir":"backen","ihr":"backt","sie":"backen"},
    "braten":  {"ich":"brate","du":"brätst","er":"brät","wir":"braten","ihr":"bratet","sie":"braten"},
    "raten":   {"ich":"rate","du":"rätst","er":"rät","wir":"raten","ihr":"ratet","sie":"raten"},
    "stoßen":  {"ich":"stoße","du":"stößt","er":"stößt","wir":"stoßen","ihr":"stoßt","sie":"stoßen"},
    "empfehlen":{"ich":"empfehle","du":"empfiehlst","er":"empfiehlt","wir":"empfehlen","ihr":"empfehlt","sie":"empfehlen"},
    "stehlen": {"ich":"stehle","du":"stiehlst","er":"stiehlt","wir":"stehlen","ihr":"stehlt","sie":"stehlen"},
    "sterben": {"ich":"sterbe","du":"stirbst","er":"stirbt","wir":"sterben","ihr":"sterbt","sie":"sterben"},
    "werfen":  {"ich":"werfe","du":"wirfst","er":"wirft","wir":"werfen","ihr":"werft","sie":"werfen"},
    "brechen": {"ich":"breche","du":"brichst","er":"bricht","wir":"brechen","ihr":"brecht","sie":"brechen"},
    "messen":  {"ich":"messe","du":"misst","er":"misst","wir":"messen","ihr":"messt","sie":"messen"},
}

SEPARABLE_PREFIXES = ("an","auf","aus","ein","mit","nach","vor","zu","weg","zurück",
                      "her","hin","fort","los","statt","teil","wieder","zusammen","ab","bei","um")


def conjugate_regular(inf):
    stem = inf[:-2]
    e = "e" if stem.endswith(("d", "t")) else ""
    if stem.endswith(("s", "ß", "z", "x")):
        du = stem + e + "t"
    else:
        du = stem + e + "st"
    return {
        "ich": stem + "e",
        "du": du,
        "er": stem + e + "t",
        "wir": inf,
        "ihr": stem + e + "t",
        "sie": inf,
    }


def get_verb_list():
    seen, verbs = set(), []
    for _, de in gq.ALL_VERBS:
        de = de.strip()
        if de in seen or "/" in de or " " in de or "-" in de:
            continue
        seen.add(de)
        if de in IRREGULAR:
            verbs.append((de, IRREGULAR[de]))
            continue
        if not de.endswith("en") or de.endswith(("eln", "ern")):
            continue
        if de.startswith(SEPARABLE_PREFIXES):
            continue
        verbs.append((de, conjugate_regular(de)))
    return verbs


def parse_noun(de):
    de = de.strip()
    if "/" in de or de.count(" ") != 1:
        return None
    article, bare = de.split(" ", 1)
    if article not in ("der", "die", "das"):
        return None
    return article, bare


def get_noun_list():
    seen, nouns = set(), []
    for _, de in gq.ALL_NOUNS:
        parsed = parse_noun(de)
        if not parsed:
            continue
        if de in seen:
            continue
        seen.add(de)
        nouns.append(parsed)
    return nouns


def get_adjective_list():
    seen, adjs = set(), []
    for _, de in gq.ALL_ADJECTIVES:
        de = de.strip()
        if "/" in de or " " in de or de in seen:
            continue
        seen.add(de)
        adjs.append(de)
    return adjs


def make_mc(question_text, correct, distractors):
    options = distractors + [correct]
    random.shuffle(options)
    return {"question": question_text, "options": options, "answer_index": options.index(correct)}


def gen_verb_forward(verbs):
    out = []
    for inf, forms in verbs:
        for person in PERSONS:
            correct = forms[person]
            others = list({v for k, v in forms.items() if k != person and v != correct})
            if len(others) < 3:
                continue
            distractors = random.sample(others, 3)
            complement = random.choice(COMPLEMENTS)
            sentence = f"{PRONOUN_TEXT[person]} ___ {complement}."
            out.append(make_mc(sentence, correct, distractors))
    return out


def gen_verb_reverse(verbs):
    out = []
    for inf, forms in verbs:
        for person in ("ich", "du"):
            verb_form = forms[person]
            correct = PRONOUN_TEXT[person]
            distractor_pool = [PRONOUN_TEXT[p] for p in PERSONS if p != person]
            distractors = random.sample(distractor_pool, 3)
            complement = random.choice(COMPLEMENTS)
            sentence = f"___ {verb_form} {complement}."
            out.append(make_mc(sentence, correct, distractors))
    return out


def gen_noun_article(nouns):
    out = []
    for article, bare in nouns:
        # Nominative
        distractors = [a for a in ("der", "die", "das", "dem") if a != article][:3]
        out.append(make_mc(f"___ {bare} ist neu.", article, distractors))
        # Accusative
        correct_acc = "den" if article == "der" else article
        acc_options = ["der", "die", "das", "den"]
        distractors_acc = [a for a in acc_options if a != correct_acc][:3]
        out.append(make_mc(f"Ich sehe ___ {bare}.", correct_acc, distractors_acc))
    return out


def gen_pronoun_agreement(nouns):
    pronoun_map = {"der": "Er", "die": "Sie", "das": "Es"}
    out = []
    for article, bare in nouns:
        correct = pronoun_map[article]
        pool = [p for p in ("Er", "Sie", "Es", "Ich", "Wir") if p != correct]
        distractors = random.sample(pool, 3)
        out.append(make_mc(f"{bare} ist hier. ___ ist neu.", correct, distractors))
    return out


def gen_adjective_ending(nouns, adjectives):
    article_map = {"der": ("ein", "er"), "die": ("eine", "e"), "das": ("ein", "es")}
    out = []
    for article, bare in nouns:
        indef, ending = article_map[article]
        adj = random.choice(adjectives)
        correct = adj + ending
        all_endings = ["er", "e", "es", "en"]
        wrong_endings = [e for e in all_endings if e != ending][:3]
        distractors = [adj + e for e in wrong_endings]
        out.append(make_mc(f"Das ist {indef} ___ {bare}.", correct, distractors))
    return out


PREPOSITIONS = [
    ("Ich fahre ___ Berlin.", "nach", ["in", "an", "zu"]),
    ("Ich fahre ___ die Schweiz.", "in", ["nach", "an", "zu"]),
    ("Sie geht ___ die Schule.", "in", ["nach", "an", "auf"]),
    ("Er wartet ___ dem Bahnhof.", "an", ["in", "auf", "zu"]),
    ("Wir sprechen ___ das Wetter.", "über", ["für", "mit", "auf"]),
    ("Das Geschenk ist ___ dich.", "für", ["mit", "über", "an"]),
    ("Ich komme ___ Nigeria.", "aus", ["von", "nach", "in"]),
    ("Sie wohnt ___ ihrer Familie.", "bei", ["mit", "für", "an"]),
    ("Er geht ___ Fuß zur Arbeit.", "zu", ["mit", "auf", "in"]),
    ("Wir fahren ___ dem Auto.", "mit", ["bei", "für", "an"]),
    ("Das Buch liegt ___ dem Tisch.", "auf", ["in", "an", "unter"]),
    ("Die Katze schläft ___ dem Bett.", "unter", ["auf", "in", "neben"]),
    ("Der Stuhl steht ___ dem Tisch.", "neben", ["unter", "auf", "in"]),
    ("Wir treffen uns ___ dem Kino.", "vor", ["hinter", "unter", "neben"]),
    ("Das Auto steht ___ dem Haus.", "hinter", ["vor", "unter", "neben"]),
]

CONJUNCTIONS = [
    ("Ich bleibe zu Hause, ___ es regnet.", "weil", ["und", "aber", "oder"]),
    ("Sie lernt Deutsch, ___ sie in Deutschland arbeiten will.", "weil", ["und", "oder", "dass"]),
    ("Ich mag Tee ___ Kaffee.", "und", ["aber", "weil", "dass"]),
    ("Er ist müde, ___ er arbeitet weiter.", "aber", ["und", "weil", "oder"]),
    ("Möchtest du Tee ___ Kaffee?", "oder", ["und", "aber", "weil"]),
    ("Ich glaube, ___ er recht hat.", "dass", ["weil", "ob", "und"]),
    ("Ich weiß nicht, ___ er kommt.", "ob", ["dass", "weil", "und"]),
    ("___ es kalt ist, ziehe ich eine Jacke an.", "Wenn", ["Weil", "Dass", "Ob"]),
    ("___ ich Zeit habe, besuche ich dich.", "Wenn", ["Dass", "Ob", "Aber"]),
    ("Sie ist klug, ___ auch fleißig.", "und", ["aber", "oder", "weil"]),
]


def gen_prepositions_conjunctions():
    out = []
    for sentence, correct, distractors in PREPOSITIONS + CONJUNCTIONS:
        out.append(make_mc(sentence, correct, distractors))
    return out


def main():
    verbs = get_verb_list()
    nouns = get_noun_list()
    adjectives = get_adjective_list()
    print(f"Usable verbs: {len(verbs)}, nouns: {len(nouns)}, adjectives: {len(adjectives)}")

    raw = []
    raw += gen_verb_forward(verbs)
    raw += gen_verb_reverse(verbs)
    raw += gen_noun_article(nouns)
    raw += gen_pronoun_agreement(nouns)
    raw += gen_adjective_ending(nouns, adjectives)
    raw += gen_prepositions_conjunctions()

    print(f"Raw grammar questions: {len(raw)}")

    seen, unique = set(), []
    for q in raw:
        k = q["question"]
        if k not in seen:
            seen.add(k)
            unique.append(q)

    random.shuffle(unique)
    unique = unique[:5000]

    questions = [{"id": f"g{i+1:04d}", **q} for i, q in enumerate(unique)]
    print(f"Total unique grammar questions: {len(questions)}")

    out = Path(__file__).parent / "data" / "grammar.json"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
