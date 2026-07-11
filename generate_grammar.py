"""
generate_grammar.py
Generates 5000+ unique German grammar fill-in-the-blank quiz questions (A2-B1):
verb conjugation, pronoun agreement, noun/article gender, adjective endings.
Each question includes an English explanation per option (why it's right/wrong).
Reuses vocabulary lists from generate_questions.py.
Output: data/grammar.json
"""
import json, random
from pathlib import Path

import generate_questions as gq  # reuses ALL_VERBS / ALL_NOUNS / ALL_ADJECTIVES

random.seed(7)

PERSONS = ["ich", "du", "er", "wir", "ihr", "sie"]
PRONOUN_TEXT = {"ich": "Ich", "du": "Du", "er": "Er", "wir": "Wir", "ihr": "Ihr", "sie": "Sie"}
PRONOUN_EN = {
    "ich": "I", "du": "you (singular, informal)", "er": "he/she/it",
    "wir": "we", "ihr": "you (plural, informal)", "sie": "they / you (formal)",
}
COMPLEMENTS = ["oft", "manchmal", "jeden Tag", "gern", "heute", "hier", "zusammen", "allein", "immer", "selten"]

GENDER_NAME = {"der": "masculine", "die": "feminine", "das": "neuter"}

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


def make_mc(question_text, correct, explain_correct, wrong_with_explain):
    """wrong_with_explain: list of (wrong_option_text, explanation_text), len==3."""
    options = [w for w, _ in wrong_with_explain] + [correct]
    explain_by_option = {w: e for w, e in wrong_with_explain}
    explain_by_option[correct] = explain_correct
    random.shuffle(options)
    answer_index = options.index(correct)
    explanations = [explain_by_option[o] for o in options]
    return {"question": question_text, "options": options, "answer_index": answer_index, "explanations": explanations}


def gen_verb_forward(verbs):
    out = []
    for inf, forms in verbs:
        for person in PERSONS:
            correct = forms[person]
            # unique (form, person-label) pairs excluding the correct one
            seen_forms = {}
            for p, f in forms.items():
                if f != correct and f not in seen_forms:
                    seen_forms[f] = p
            if len(seen_forms) < 3:
                continue
            wrong_forms = random.sample(list(seen_forms.items()), 3)
            complement = random.choice(COMPLEMENTS)
            sentence = f"{PRONOUN_TEXT[person]} ___ {complement}."
            explain_correct = (
                f"'{correct}' is correct — it is the present-tense form of '{inf}' "
                f"for '{PRONOUN_TEXT[person]}' ({PRONOUN_EN[person]})."
            )
            wrong_with_explain = [
                (f, f"'{f}' is incorrect — that is the form of '{inf}' used with "
                    f"'{PRONOUN_TEXT[p]}' ({PRONOUN_EN[p]}), not '{PRONOUN_TEXT[person]}'.")
                for f, p in wrong_forms
            ]
            out.append(make_mc(sentence, correct, explain_correct, wrong_with_explain))
    return out


def gen_verb_reverse(verbs):
    out = []
    for inf, forms in verbs:
        for person in ("ich", "du"):
            verb_form = forms[person]
            correct = PRONOUN_TEXT[person]
            distractor_persons = random.sample([p for p in PERSONS if p != person], 3)
            complement = random.choice(COMPLEMENTS)
            sentence = f"___ {verb_form} {complement}."
            explain_correct = (
                f"'{correct}' is correct — '{verb_form}' is the '{inf}' form used with "
                f"'{correct}' ({PRONOUN_EN[person]})."
            )
            wrong_with_explain = [
                (PRONOUN_TEXT[p], f"'{PRONOUN_TEXT[p]}' is incorrect — '{verb_form}' does not match "
                                   f"the '{inf}' conjugation for '{PRONOUN_TEXT[p]}' ({PRONOUN_EN[p]}).")
                for p in distractor_persons
            ]
            out.append(make_mc(sentence, correct, explain_correct, wrong_with_explain))
    return out


def gen_noun_article(nouns):
    out = []
    for article, bare in nouns:
        gender = GENDER_NAME[article]
        # Nominative
        wrong_articles = [a for a in ("der", "die", "das", "dem") if a != article][:3]
        explain_correct = f"'{article}' is correct — '{bare}' is a {gender} noun ('{article} {bare}')."
        wrong_with_explain = [
            (a, f"'{a}' is incorrect — '{bare}' is {gender} ('{article} {bare}'), not the gender/case '{a}' marks.")
            for a in wrong_articles
        ]
        out.append(make_mc(f"___ {bare} ist neu.", article, explain_correct, wrong_with_explain))

        # Accusative
        correct_acc = "den" if article == "der" else article
        acc_options = ["der", "die", "das", "den"]
        wrong_acc = [a for a in acc_options if a != correct_acc][:3]
        if article == "der":
            explain_correct_acc = (
                f"'den' is correct — masculine nouns like '{bare}' change 'der' to 'den' "
                f"in the accusative case (the direct object of 'sehen')."
            )
        else:
            explain_correct_acc = (
                f"'{correct_acc}' is correct — {gender} nouns like '{bare}' keep the article "
                f"'{correct_acc}' in the accusative case (only masculine 'der' changes to 'den')."
            )
        wrong_with_explain_acc = [
            (a, f"'{a}' is incorrect — the accusative form of '{article} {bare}' is '{correct_acc}', not '{a}'.")
            for a in wrong_acc
        ]
        out.append(make_mc(f"Ich sehe ___ {bare}.", correct_acc, explain_correct_acc, wrong_with_explain_acc))
    return out


def gen_pronoun_agreement(nouns):
    pronoun_map = {"der": "Er", "die": "Sie", "das": "Es"}
    out = []
    for article, bare in nouns:
        gender = GENDER_NAME[article]
        correct = pronoun_map[article]
        pool = [p for p in ("Er", "Sie", "Es", "Ich", "Wir") if p != correct]
        wrong = random.sample(pool, 3)
        explain_correct = f"'{correct}' is correct — '{bare}' is {gender} ('{article} {bare}'), so it is replaced by '{correct}'."
        wrong_with_explain = [
            (w, f"'{w}' is incorrect — '{bare}' is {gender} ('{article} {bare}'), which is replaced by '{correct}', not '{w}'.")
            for w in wrong
        ]
        out.append(make_mc(f"{bare} ist hier. ___ ist neu.", correct, explain_correct, wrong_with_explain))
    return out


def gen_adjective_ending(nouns, adjectives):
    article_map = {"der": ("ein", "er"), "die": ("eine", "e"), "das": ("ein", "es")}
    out = []
    for article, bare in nouns:
        gender = GENDER_NAME[article]
        indef, ending = article_map[article]
        adj = random.choice(adjectives)
        correct = adj + ending
        all_endings = ["er", "e", "es", "en"]
        wrong_endings = [e for e in all_endings if e != ending][:3]
        explain_correct = (
            f"'{correct}' is correct — after '{indef}' the adjective takes the '-{ending}' ending "
            f"to agree with the {gender} noun '{bare}'."
        )
        wrong_with_explain = [
            (adj + e, f"'{adj+e}' is incorrect — the '-{e}' ending does not agree with the {gender} noun '{bare}' after '{indef}'.")
            for e in wrong_endings
        ]
        out.append(make_mc(f"Das ist {indef} ___ {bare}.", correct, explain_correct, wrong_with_explain))
    return out


# Each entry: (sentence, correct, [(wrong, explanation), ...], explanation_for_correct)
PREPOSITIONS = [
    ("Ich fahre ___ Berlin.", "nach", "'nach' is correct — it is used before city/country names without an article to express travel destination.",
        [("in", "'in' is used with places that take an article (e.g. 'in die Schweiz'), not with city names like 'Berlin'."),
         ("an", "'an' expresses proximity to something (a border, a lake), not travel to a city."),
         ("zu", "'zu' is used for travel to a person or a specific nearby place, not to name a city as a destination.")]),
    ("Ich fahre ___ die Schweiz.", "in", "'in' is correct — countries with an article (die Schweiz) use 'in' for travel destination.",
        [("nach", "'nach' is used for cities and countries WITHOUT an article, but 'die Schweiz' has an article, so 'in' is needed."),
         ("an", "'an' expresses proximity, not travel into a country."),
         ("zu", "'zu' is used for travel to a person or nearby place, not into a country.")]),
    ("Sie geht ___ die Schule.", "in", "'in' is correct — 'in die Schule gehen' expresses going into the school building.",
        [("nach", "'nach' is not used with 'die Schule' (a place with an article)."),
         ("an", "'an' expresses being at the edge/border of something, not entering a building."),
         ("auf", "'auf' is used with some institutions (auf die Universität) but not standardly with 'die Schule'.")]),
    ("Er wartet ___ dem Bahnhof.", "an", "'an' is correct — 'am Bahnhof warten' means waiting at the station.",
        [("in", "'in' would mean waiting inside the station building, which changes the meaning."),
         ("auf", "'auf jemanden/etwas warten' means 'to wait for' someone/something, not 'at' a place."),
         ("zu", "'zu' expresses direction toward, not the location of waiting.")]),
    ("Wir sprechen ___ das Wetter.", "über", "'über' is correct — 'über etwas sprechen' means 'to talk about something'.",
        [("für", "'für' means 'for', which doesn't fit 'to talk about'."),
         ("mit", "'mit' means talking 'with' someone, not 'about' a topic."),
         ("auf", "'auf' does not combine with 'sprechen' to mean 'about'.")]),
    ("Das Geschenk ist ___ dich.", "für", "'für' is correct — 'für dich' means 'for you', showing who the gift is intended for.",
        [("mit", "'mit' means 'with', not 'for'."),
         ("über", "'über' means 'about/over', which doesn't fit here."),
         ("an", "'an' would suggest addressing something to a place or person differently, not 'intended for'.")]),
    ("Ich komme ___ Nigeria.", "aus", "'aus' is correct — 'aus einem Land kommen' expresses origin/where someone is from.",
        [("von", "'von' expresses 'from' in the sense of starting point of movement, not nationality/origin."),
         ("nach", "'nach' expresses destination ('to'), not origin ('from')."),
         ("in", "'in' expresses location inside, not origin.")]),
    ("Sie wohnt ___ ihrer Familie.", "bei", "'bei' is correct — 'bei jemandem wohnen' means 'to live with/at someone's place'.",
        [("mit", "'mit' means accompanying someone, but living AT someone's place uses 'bei'."),
         ("für", "'für' means 'for', which doesn't fit 'to live at'."),
         ("an", "'an' doesn't combine with 'wohnen' to mean 'with someone'.")]),
    ("Er geht ___ Fuß zur Arbeit.", "zu", "'zu Fuß gehen' is a fixed expression meaning 'to walk/go on foot'.",
        [("mit", "'mit Fuß' is not correct German; the fixed phrase is 'zu Fuß'."),
         ("auf", "'auf Fuß' is not a valid German expression."),
         ("in", "'in Fuß' is not a valid German expression.")]),
    ("Wir fahren ___ dem Auto.", "mit", "'mit dem Auto fahren' means 'to travel by car' — 'mit' expresses the means of transport.",
        [("bei", "'bei' does not express means of transport."),
         ("für", "'für' means 'for', not 'by means of'."),
         ("an", "'an' does not combine with vehicles to mean 'by'.")]),
    ("Das Buch liegt ___ dem Tisch.", "auf", "'auf' is correct — 'auf dem Tisch' means 'on the table' (on top of a surface).",
        [("in", "'in' would mean inside the table, not on its surface."),
         ("an", "'an' means 'against/next to', not 'on top of'."),
         ("unter", "'unter' means 'under', the opposite of the intended meaning.")]),
    ("Die Katze schläft ___ dem Bett.", "unter", "'unter dem Bett' means 'under the bed' — matching a cat hiding underneath.",
        [("auf", "'auf dem Bett' would mean 'on the bed', not underneath it."),
         ("in", "'in dem Bett' would mean inside/in the bed itself, not beneath it."),
         ("neben", "'neben' means 'next to', not 'underneath'.")]),
    ("Der Stuhl steht ___ dem Tisch.", "neben", "'neben dem Tisch' means 'next to the table'.",
        [("unter", "'unter' means 'under', not 'next to'."),
         ("auf", "'auf' means 'on top of', not 'next to'."),
         ("in", "'in' means 'inside', not 'next to'.")]),
    ("Wir treffen uns ___ dem Kino.", "vor", "'vor dem Kino' means 'in front of the cinema', a common meeting spot.",
        [("hinter", "'hinter' means 'behind', not 'in front of'."),
         ("unter", "'unter' means 'under', which doesn't fit meeting outside a building."),
         ("neben", "'neben' means 'next to' — possible but not the intended 'in front of' meaning here.")]),
    ("Das Auto steht ___ dem Haus.", "hinter", "'hinter dem Haus' means 'behind the house'.",
        [("vor", "'vor' means 'in front of', the opposite of 'behind'."),
         ("unter", "'unter' means 'under', not 'behind'."),
         ("neben", "'neben' means 'next to', not 'behind'.")]),
]

CONJUNCTIONS = [
    ("Ich bleibe zu Hause, ___ es regnet.", "weil", "'weil' (because) is correct — it introduces the reason for staying home.",
        [("und", "'und' (and) just connects two ideas; it doesn't give a reason."),
         ("aber", "'aber' (but) signals contrast, not a reason."),
         ("oder", "'oder' (or) presents an alternative, not a reason.")]),
    ("Sie lernt Deutsch, ___ sie in Deutschland arbeiten will.", "weil", "'weil' (because) correctly introduces the reason she is learning German.",
        [("und", "'und' just adds information; it doesn't explain 'why'."),
         ("oder", "'oder' presents an alternative, not a reason."),
         ("dass", "'dass' (that) introduces a fact/content clause, not a cause.")]),
    ("Ich mag Tee ___ Kaffee.", "und", "'und' (and) correctly joins two liked things.",
        [("aber", "'aber' (but) signals a contrast, which doesn't fit simply listing two liked drinks."),
         ("weil", "'weil' (because) would need a reason clause, not a second liked item."),
         ("dass", "'dass' (that) introduces a subordinate clause, not a simple list.")]),
    ("Er ist müde, ___ er arbeitet weiter.", "aber", "'aber' (but) is correct — it shows the contrast between being tired and continuing to work.",
        [("und", "'und' (and) doesn't capture the contrast between being tired and still working."),
         ("weil", "'weil' (because) would suggest tiredness is why he continues, which reverses the logic."),
         ("oder", "'oder' (or) presents an alternative, not a contrast.")]),
    ("Möchtest du Tee ___ Kaffee?", "oder", "'oder' (or) is correct — it presents a choice between two drinks.",
        [("und", "'und' (and) would mean offering both together, not a choice."),
         ("aber", "'aber' (but) signals contrast, not a choice between options."),
         ("weil", "'weil' (because) doesn't fit a question offering a choice.")]),
    ("Ich glaube, ___ er recht hat.", "dass", "'dass' (that) correctly introduces the content clause of what is believed.",
        [("weil", "'weil' (because) would introduce a reason, not the content of the belief."),
         ("ob", "'ob' (whether) is used for uncertainty/questions, not a confident belief statement."),
         ("und", "'und' (and) doesn't introduce a subordinate content clause.")]),
    ("Ich weiß nicht, ___ er kommt.", "ob", "'ob' (whether/if) is correct — it introduces uncertainty about whether he is coming.",
        [("dass", "'dass' (that) would state a fact, but here there's uncertainty, so 'ob' is needed."),
         ("weil", "'weil' (because) would introduce a reason, not an uncertain outcome."),
         ("und", "'und' (and) doesn't fit introducing an uncertain clause.")]),
    ("___ es kalt ist, ziehe ich eine Jacke an.", "Wenn", "'Wenn' (when/if) correctly introduces the condition for putting on a jacket.",
        [("Weil", "'Weil' (because) would state a reason rather than a condition."),
         ("Dass", "'Dass' (that) introduces a content clause, not a conditional one."),
         ("Ob", "'Ob' (whether) introduces uncertainty, not a condition.")]),
    ("___ ich Zeit habe, besuche ich dich.", "Wenn", "'Wenn' (when/if) correctly introduces the condition for the visit.",
        [("Dass", "'Dass' (that) introduces a fact, not a condition."),
         ("Ob", "'Ob' (whether) introduces uncertainty, not a condition."),
         ("Aber", "'Aber' (but) signals contrast and cannot start a conditional clause like this.")]),
    ("Sie ist klug, ___ auch fleißig.", "und", "'und' (and) correctly adds a second matching quality.",
        [("aber", "'aber' (but) would signal contrast, but 'fleißig' complements 'klug' rather than contrasting."),
         ("oder", "'oder' (or) presents an alternative, not an addition."),
         ("weil", "'weil' (because) doesn't fit simply adding another quality.")]),
]


def gen_prepositions_conjunctions():
    out = []
    for sentence, correct, explain_correct, wrong_with_explain in PREPOSITIONS + CONJUNCTIONS:
        out.append(make_mc(sentence, correct, explain_correct, wrong_with_explain))
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
