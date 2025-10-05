# streamlit_app.py (fix)
import streamlit as st
import json
from io import BytesIO
import random
import unicodedata

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ---------------- Utils ----------------
def normalize(s: str) -> str:
    s = s.strip().lower()
    s = " ".join(s.split())
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s

DEFAULT_STORE = {
    "collections": [
        {
            "name": "Evolution_und_Steinzeit",
            "items": [
                {"de": "die Urgeschichte", "fr": "la Préhistoire"},
                {"de": "die Frühgeschichte", "fr": "la Protohistoire"},
                {"de": "die Altsteinzeit (2,5 Mio.-9500 v. Chr.)", "fr": "le Paléolithique"},
                {"de": "die Jungsteinzeit (9500 v. Chr.-2200 v. Chr.)", "fr": "le Néolithique"},
                {"de": "der Archäologe", "fr": "l'archéologue"},
                {"de": "die Höhlenmalerei", "fr": "la peinture pariétale"},
                {"de": "der Nomade, die Nomadin", "fr": "un/une nomade"},
                {"de": "roden, urbar machen", "fr": "défricher"},
                {"de": "der/die Sesshafte", "fr": "le/la sédentaire"},
                {"de": "sesshaft werden", "fr": "devenir sédentaire"},
                {"de": "der Tauschhandel", "fr": "le troc"},
                {"de": "der Jäger und Sammler", "fr": "le chasseur-cueilleur"},
                {"de": "der Faustkeil", "fr": "le biface en silex"},
                {"de": "das Haustier", "fr": "l'animal domestique"},
            ]
        }
    ]
}

def import_docx(file_bytes, filename):
    if not DOCX_AVAILABLE:
        st.error("python-docx ist nicht installiert – bitte in requirements hinzufügen.")
        return None
    doc = Document(BytesIO(file_bytes))
    items = []

    # Tabellen (2 Spalten: DE | FR)
    for tbl in doc.tables:
        for r_i, row in enumerate(tbl.rows):
            cells = [c.text.strip() for c in row.cells]
            if len(cells) >= 2:
                de, fr = cells[0], cells[1]
                if not de or not fr:
                    continue
                if r_i == 0 and ("de" in de.lower() and "fr" in fr.lower()):
                    # Überschriftenzeile
                    continue
                items.append({"de": de, "fr": fr})

    # Absätze mit "de ; fr"
    for p in doc.paragraphs:
        t = p.text.strip()
        if ";" in t:
            parts = [s.strip() for s in t.split(";")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                items.append({"de": parts[0], "fr": parts[1]})

    # Dedupe
    seen = set(); uniq = []
    for it in items:
        key = (normalize(it["de"]), normalize(it["fr"]))
        if key in seen:
            continue
        seen.add(key); uniq.append(it)
    return {"name": filename.rsplit(".",1)[0], "items": uniq}

# --------------- App -------------------
st.set_page_config(page_title="VocabQuiz DE↔FR", page_icon="🔤", layout="wide")
st.title("VocabQuiz – Deutsch ↔ Français")

# Session init
if "store" not in st.session_state:
    st.session_state.store = DEFAULT_STORE
if "quiz" not in st.session_state:
    st.session_state.quiz = None  # dict | None

tab_quiz, tab_manage = st.tabs(["🎯 Quiz", "📚 Sammlungen & Import"])

# ---------- Manage ----------
with tab_manage:
    st.subheader("Bestehende Sammlungen")
    for c in st.session_state.store.get("collections", []):
        st.markdown(f"- **{c.get('name')}** – {len(c.get('items', []))} Einträge")
    st.divider()

    st.subheader("Import aus Word (.docx)")
    up = st.file_uploader("Word-Datei hochladen", type=["docx"])
    if up is not None:
        data = import_docx(up.read(), up.name)
        if data and len(data["items"]) > 0:
            if st.button(f"Sammlung '{data['name']}' importieren ({len(data['items'])} Einträge)"):
                cols = st.session_state.store["collections"]
                idx = next((i for i, c in enumerate(cols) if c.get("name") == data["name"]), None)
                if idx is not None:
                    cols[idx] = data
                else:
                    cols.append(data)
                st.success(f"Importiert: {len(data['items'])} Einträge in '{data['name']}'")

    st.divider()
    st.subheader("Datenbank exportieren")
    js = json.dumps(st.session_state.store, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("vocab_store.json herunterladen", js, file_name="vocab_store.json", mime="application/json")

# ---------- Quiz ----------
with tab_quiz:
    cols = ["(alle)"] + [c.get("name", "?") for c in st.session_state.store.get("collections", [])]
    coll = st.selectbox("Sammlung", cols, index=0)
    direction = st.radio("Richtung", ["DE→FR", "FR→DE"], horizontal=True)
    mode = st.radio("Quiztyp", ["Multiple Choice", "Freitext"], horizontal=True)
    n_q = st.slider("Anzahl Fragen", 5, 50, 10)

    # Build pool
    pool = []
    for c in st.session_state.store.get("collections", []):
        if coll != "(alle)" and c.get("name") != coll:
            continue
        pool.extend(c.get("items", []))

    start = st.button("Quiz starten", type="primary", use_container_width=False)
    if start and len(pool) >= 4:
        st.session_state.quiz = {
            "pool": pool[:],  # vollständiger Pool für Distraktoren
            "direction": direction,
            "mode": mode,
            "questions": random.sample(pool, min(n_q, len(pool))),
            "index": 0,
            "score": 0,
            "history": []
        }

    q = st.session_state.quiz
    if q is None:
        st.info("Konfiguration wählen und **Quiz starten**.")
        st.stop()

    idx = q["index"]
    total = len(q["questions"])

    if idx < total:
        it = q["questions"][idx]
        question = it["de"] if q["direction"] == "DE→FR" else it["fr"]
        answer = it["fr"] if q["direction"] == "DE→FR" else it["de"]

        st.info(f"Frage {idx+1}/{total}  •  Punktzahl: {q['score']}")
        st.write(f"**Übersetze:** {question}")

        # Alle möglichen Antworten (für Distraktoren) aus dem vollen Pool
        if q["direction"] == "DE→FR":
            all_answers = list({ x["fr"] for x in q["pool"] })
        else:
            all_answers = list({ x["de"] for x in q["pool"] })

        # ---- Eingabe in einer Form (stabiler Submit) ----
        with st.form(key=f"form_q_{idx}", clear_on_submit=False):
            user_answer = None
            if q["mode"] == "Multiple Choice":
                # 1 richtige + bis zu 3 falsche
                distractors = [a for a in all_answers if normalize(a) != normalize(answer)]
                random.shuffle(distractors)
                options = [answer] + distractors[:3]
                random.shuffle(options)
                user_answer = st.radio("Wähle die richtige Übersetzung:", options, index=None, key=f"radio_{idx}")
            else:
                user_answer = st.text_input("Antwort eingeben", key=f"text_{idx}")

            submitted = st.form_submit_button("Weiter", use_container_width=True)

        if submitted:
            if (q["mode"] == "Multiple Choice" and user_answer is None) or \
               (q["mode"] == "Freitext" and not user_answer.strip()):
                st.warning("Bitte eine Antwort eingeben/auswählen.")
            else:
                ok = normalize(user_answer) == normalize(answer)
                if ok:
                    q["score"] += 1
                    st.success("Richtig!")
                else:
                    st.error(f"Falsch. Richtige Antwort: **{answer}**")
                q["history"].append((question, user_answer, ok, answer))
                q["index"] += 1
                st.rerun()
    else:
        # Ergebnis
        st.success(f"Fertig! Punktzahl: {q['score']}/{total}  ({round(100*q['score']/max(1,total))}%)")
        st.dataframe(
            [{"Frage":h[0], "Ihre Antwort":h[1], "Korrekt":"Ja" if h[2] else "Nein", "Richtig":h[3]} for h in q["history"]],
            use_container_width=True
        )
        col1, col2 = st.columns(2)
        if col1.button("Neues Quiz", use_container_width=True):
            st.session_state.quiz = None
            st.rerun()
        if col2.button("Nochmal gleiche Auswahl", use_container_width=True):
            # gleiche Einstellungen, neue Fragen
            st.session_state.quiz = {
                "pool": pool[:],
                "direction": direction,
                "mode": mode,
                "questions": random.sample(pool, min(n_q, len(pool))),
                "index": 0,
                "score": 0,
                "history": []
            }
            st.rerun()
