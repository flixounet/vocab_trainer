# streamlit_app.py
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

if "store" not in st.session_state:
    st.session_state.store = DEFAULT_STORE

def import_docx(file_bytes, filename):
    if not DOCX_AVAILABLE:
        st.error("python-docx ist nicht installiert – bitte in requirements hinzufügen.")
        return None
    doc = Document(BytesIO(file_bytes))
    items = []
    for tbl in doc.tables:
        for r_i, row in enumerate(tbl.rows):
            cells = [c.text.strip() for c in row.cells]
            if len(cells) >= 2:
                de, fr = cells[0], cells[1]
                if not de or not fr: continue
                if r_i == 0 and ("de" in de.lower() and "fr" in fr.lower()):
                    continue
                items.append({"de": de, "fr": fr})
    for p in doc.paragraphs:
        t = p.text.strip()
        if ";" in t:
            parts = [s.strip() for s in t.split(";")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                items.append({"de": parts[0], "fr": parts[1]})
    seen = set(); uniq = []
    for it in items:
        key = (normalize(it["de"]), normalize(it["fr"]))
        if key in seen: continue
        seen.add(key); uniq.append(it)
    return {"name": filename.rsplit(".",1)[0], "items": uniq}

st.set_page_config(page_title="VocabQuiz DE↔FR", page_icon="🔤", layout="wide")
st.title("VocabQuiz – Deutsch ↔ Français")

tab_quiz, tab_manage = st.tabs(["🎯 Quiz", "📚 Sammlungen & Import"])

with tab_manage:
    st.subheader("Bestehende Sammlungen")
    for c in st.session_state.store.get("collections", []):
        st.markdown(f"- **{c.get('name')}** – {len(c.get('items', []))} Einträge")
    st.divider()
    st.subheader("Import aus Word (.docx)")
    up = st.file_uploader("Word-Datei hochladen", type=["docx"])
    if up is not None:
        data = import_docx(up.read(), up.name)
        if data and len(data["items"])>0:
            if st.button(f"Sammlung '{data['name']}' importieren ({len(data['items'])} Einträge)"):
                cols = st.session_state.store["collections"]
                idx = next((i for i,c in enumerate(cols) if c.get("name")==data["name"]), None)
                if idx is not None:
                    cols[idx] = data
                else:
                    cols.append(data)
                st.success(f"Importiert: {len(data['items'])} Einträge in '{data['name']}'")
    st.divider()
    st.subheader("Datenbank exportieren")
    js = json.dumps(st.session_state.store, ensure_ascii=False, indent=2).encode("utf-8")
    st.download_button("vocab_store.json herunterladen", js, file_name="vocab_store.json", mime="application/json")

with tab_quiz:
    cols = [ "(alle)" ] + [c.get("name","?") for c in st.session_state.store.get("collections", [])]
    coll = st.selectbox("Sammlung", cols, index=0)
    direction = st.radio("Richtung", ["DE→FR", "FR→DE"], horizontal=True)
    mode = st.radio("Quiztyp", ["Multiple Choice", "Freitext"], horizontal=True)
    n_q = st.slider("Anzahl Fragen", 5, 50, 10)
    pool = []
    for c in st.session_state.store.get("collections", []):
        if coll != "(alle)" and c.get("name") != coll:
            continue
        for it in c.get("items", []):
            pool.append(it)
    if st.button("Quiz starten") and len(pool)>=4:
        st.session_state.quiz = {
            "pool": pool,
            "direction": direction,
            "mode": mode,
            "questions": random.sample(pool, min(n_q, len(pool))),
            "index": 0,
            "score": 0,
            "history": []
        }
    if "quiz" in st.session_state:
        q = st.session_state.quiz
        idx = q["index"]
        if idx < len(q["questions"]):
            it = q["questions"][idx]
            question = it["de"] if q["direction"]=="DE→FR" else it["fr"]
            answer = it["fr"] if q["direction"]=="DE→FR" else it["de"]
            st.info(f"Frage {idx+1}/{len(q['questions'])}  •  Punktzahl: {q['score']}")
            st.write(f"**Übersetze:** {question}")
            if q["mode"] == "Multiple Choice":
                all_ans = list({ (x["fr"] if q["direction"]=="DE→FR" else x["de"]) for x in q["questions"] })
                if answer not in all_ans: all_ans.append(answer)
                random.shuffle(all_ans)
                opts = [answer]
                for cand in all_ans:
                    if cand == answer: continue
                    if len(opts)>=4: break
                    opts.append(cand)
                random.shuffle(opts)
                user_answer = st.radio("Wähle die richtige Übersetzung:", opts, index=None)
                if st.button("Weiter", use_container_width=True, type="primary", disabled=user_answer is None):
                    if user_answer is None: st.stop()
                    ok = normalize(user_answer)==normalize(answer)
                    q["score"] += 1 if ok else 0
                    q["history"].append((question, user_answer, ok, answer))
                    q["index"] += 1
                    st.experimental_rerun()
            else:
                user_answer = st.text_input("Antwort eingeben")
                if st.button("Weiter", use_container_width=True, type="primary"):
                    if not user_answer.strip(): st.stop()
                    ok = normalize(user_answer)==normalize(answer)
                    q["score"] += 1 if ok else 0
                    q["history"].append((question, user_answer, ok, answer))
                    q["index"] += 1
                    st.experimental_rerun()
        else:
            total = len(q["questions"])
            st.success(f"Fertig! Punktzahl: {q['score']}/{total}  ({round(100*q['score']/max(1,total))}%)")
            st.dataframe(
                [{"Frage":h[0], "Ihre Antwort":h[1], "Korrekt": "Ja" if h[2] else "Nein", "Richtig": h[3]} for h in q["history"]],
                use_container_width=True
            )
            if st.button("Neues Quiz"):
                del st.session_state["quiz"]
                st.experimental_rerun()
