
# app.py
import streamlit as st
import pandas as pd
import json, os, time
from datetime import datetime
from questions import questions

st.set_page_config(page_title="QCM MAZAVA", layout="wide")

RESULTS_FILE = "resultats.csv"

if "started" not in st.session_state:
    st.session_state.started = False
if "user" not in st.session_state:
    st.session_state.user = ""
if "current_q" not in st.session_state:
    st.session_state.current_q = 0
if "answers" not in st.session_state:
    st.session_state.answers = []
if "start_time" not in st.session_state:
    st.session_state.start_time = time.time()

menu = st.sidebar.radio(
    "Menu",
    ["Passer le QCM", "Classement", "Détail des réponses"]
)

if menu == "Passer le QCM":
    st.title("💡 Evaluation MAZAVA")

    seconds_per_question = st.sidebar.number_input(
        "Temps par question (secondes)",
        min_value=10,
        max_value=300,
        value=60
    )

    if not st.session_state.started:
        username = st.text_input("Nom d'utilisateur")

        if st.button("Commencer l'examen"):
            if not username.strip():
                st.error("Entrer un nom.")
                st.stop()

            if os.path.exists(RESULTS_FILE):
                df = pd.read_csv(RESULTS_FILE)
                if "Nom" in df.columns and username.lower() in df["Nom"].astype(str).str.lower().values:
                    st.error("Cet utilisateur a déjà passé le test.")
                    st.stop()

            st.session_state.user = username
            st.session_state.started = True
            st.session_state.current_q = 0
            st.session_state.answers = []
            st.session_state.start_time = time.time()
            st.rerun()

    else:
        q_index = st.session_state.current_q

        if q_index >= len(questions):

            score = 0

            for i, q in enumerate(questions):
                rep = st.session_state.answers[i]

                if q["type"] == "simple":
                    if rep == q["reponse"]:
                        score += 1
                else:
                    bonnes = set(q["reponse"])
                    choisies = set(rep if rep else [])
                    score_question = len(bonnes & choisies) / len(bonnes)
                    score_question -= len(choisies - bonnes) * 0.25
                    score += max(0, score_question)

            note = round(score / len(questions) * 20, 2)

            row = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Nom": st.session_state.user,
                "Score": round(score, 2),
                "Total": len(questions),
                "Note": note,
                "Reponses": json.dumps(st.session_state.answers, ensure_ascii=False)
            }])

            if os.path.exists(RESULTS_FILE):
                row.to_csv(RESULTS_FILE, mode="a", header=False, index=False)
            else:
                row.to_csv(RESULTS_FILE, index=False)

            st.success("Examen terminé")
            st.metric("Note", f"{note}/20")

            if st.button("Nouvelle session"):
                for k in ["started","user","current_q","answers","start_time"]:
                    st.session_state.pop(k, None)
                st.rerun()

        else:
            q = questions[q_index]

            elapsed = int(time.time() - st.session_state.start_time)
            remaining = seconds_per_question - elapsed

            progress = q_index / len(questions)
            st.progress(progress)

            st.subheader(f"Question {q_index+1}/{len(questions)}")
            st.metric("Temps restant", max(remaining, 0))

            if remaining <= 0:
                st.session_state.answers.append(None)
                st.session_state.current_q += 1
                st.session_state.start_time = time.time()
                st.rerun()

            st.write(q["question"])

            if q["type"] == "simple":
                rep = st.radio("Réponse", q["options"], key=f"q_{q_index}")
            else:
                rep = st.multiselect("Réponses", q["options"], key=f"q_{q_index}")

            if st.button("Valider la réponse"):
                st.session_state.answers.append(rep)
                st.session_state.current_q += 1
                st.session_state.start_time = time.time()
                st.rerun()

            time.sleep(1)
            st.rerun()

elif menu == "Classement":
    st.title("🏆 Classement")

    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE)
        df = df.sort_values("Note", ascending=False)
        st.dataframe(df[["Nom", "Score", "Note"]], use_container_width=True)
    else:
        st.info("Aucun résultat.")

elif menu == "Détail des réponses":
    st.title("📋 Détail des réponses")

    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE)

        if "Reponses" not in df.columns:
            st.error("La colonne Reponses est absente.")
            st.stop()

        user = st.selectbox("Participant", df["Nom"])

        row = df[df["Nom"] == user].iloc[0]

        st.write(f"**Note :** {row['Note']}/20")

        reps = json.loads(row["Reponses"])

        for i, q in enumerate(questions):
            st.markdown("---")
            st.write(f"**{q['question']}**")
            st.write("Réponse utilisateur :", reps[i])
            st.write("Bonne réponse :", q["reponse"])
    else:
        st.info("Aucun résultat.")
