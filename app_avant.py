import streamlit as st
import pandas as pd
import os
import json
import random
import sqlite3
from datetime import datetime
from questions import questions

st.set_page_config(
    page_title="QCM MAZAVA",
    page_icon="💡",
    layout="wide"
)

DB_NAME = "resultats_qcm.db"
TEMPS_PAR_QUESTION = 30  # 30 secondes par question

# ==================================
# FONCTIONS DE LA BASE DE DONNÉES (SQLITE)
# ==================================
def initialiser_bdd():
    """Crée la table des résultats si elle n'existe pas encore."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resultats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            lieu TEXT,
            nom TEXT,
            score REAL,
            total INTEGER,
            note REAL,
            reponses TEXT,
            details_reussite TEXT
        )
    """)
    conn.commit()
    conn.close()

def utilisateur_existe(nom, lieu):
    """Vérifie si un utilisateur a déjà passé le test pour un lot donné."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM resultats WHERE LOWER(nom) = ? AND LOWER(lieu) = ?", 
        (nom.lower().strip(), lieu.lower().strip())
    )
    existe = cursor.fetchone() is not None
    conn.close()
    return existe

def sauvegarder_resultat(lieu, nom, score, total, note, reponses_json, details_json):
    """Insère un nouveau résultat en base de données."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO resultats (date, lieu, nom, score, total, note, reponses, details_reussite)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        lieu, nom, score, total, note, reponses_json, details_json
    ))
    conn.commit()
    conn.close()

def charger_tous_les_resultats():
    """Récupère l'historique global sous forme de DataFrame Pandas."""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM resultats", conn)
    conn.close()
    return df

# Initialisation de la BDD au démarrage
initialiser_bdd()

# ==================================
# INITIALISATION DES ÉTATS (SESSION STATE)
# ==================================
if "qcm_etape" not in st.session_state:
    st.session_state.qcm_etape = "accueil"
if "index_question" not in st.session_state:
    st.session_state.index_question = 0
if "reponses_utilisateur" not in st.session_state:
    st.session_state.reponses_utilisateur = []
if "nom_utilisateur" not in st.session_state:
    st.session_state.nom_utilisateur = ""
if "lieu_utilisateur" not in st.session_state:
    st.session_state.lieu_utilisateur = ""
if "liste_questions" not in st.session_state:
    st.session_state.liste_questions = []

# ==================================
# INJECTION CSS (Masquage du bouton technique)
# ==================================
st.markdown(
    """
    <style>
        button[key="timeout_btn"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ==================================
# MENU (Verrouillé pendant l'évaluation)
# ==================================
if "qcm_etape" in st.session_state and st.session_state.qcm_etape == "en_cours":
    st.sidebar.warning("⏳ Évaluation en cours... Menu désactivé.")
    menu = "Passer le QCM"
else:
    menu = st.sidebar.radio(
        "Menu",
        ["Passer le QCM", "Classement", "Détail des réponses"]
    )

# Fonction de transition
def passer_a_la_suivante(reponse_actuelle):
    st.session_state.reponses_utilisateur.append(reponse_actuelle)
    st.session_state.index_question += 1
    
    if st.session_state.index_question >= len(st.session_state.liste_questions):
        st.session_state.qcm_etape = "termine"
    st.rerun()

# ==================================
# PASSER LE QCM
# ==================================
if menu == "Passer le QCM":
    st.title("💡 Évaluation Projet MAZAVA")

    # --- ACCUEIL ---
    if st.session_state.qcm_etape == "accueil":
        # Remplacement complet des anciens centres par vos 4 LOTS
        lieu_selectionne = st.selectbox(
            "Sélectionnez votre LOT", 
            ["LOT 8 CONNECT", "LOT 9 YMAD", "LOT 5 YMAD", "LOT 10 CONSORTIUM"]
        )
        nom = st.text_input("Nom d'utilisateur").strip()
        
        if nom and lieu_selectionne:
            if utilisateur_existe(nom, lieu_selectionne):
                st.error(f"L'utilisateur '{nom}' a déjà passé l'évaluation pour le '{lieu_selectionne}'.")
                st.stop()

            if st.button("Commencer l'évaluation"):
                st.session_state.nom_utilisateur = nom
                st.session_state.lieu_utilisateur = lieu_selectionne
                st.session_state.index_question = 0
                st.session_state.reponses_utilisateur = []
                
                # Shuffling questions & options
                prep_questions = []
                for idx, q in enumerate(questions):
                    opts = q["options"].copy()
                    random.shuffle(opts)
                    prep_questions.append({
                        "id_original": idx, 
                        "question": q["question"],
                        "type": q["type"],
                        "options": opts,
                        "reponse": q["reponse"]
                    })
                random.shuffle(prep_questions)
                
                st.session_state.liste_questions = prep_questions
                st.session_state.qcm_etape = "en_cours"
                st.rerun()

    # --- TEST EN COURS ---
    elif st.session_state.qcm_etape == "en_cours":
        i = st.session_state.index_question
        q = st.session_state.liste_questions[i]
        
        st.subheader(f"Question {i + 1} / {len(st.session_state.liste_questions)}")
        
        bt_timeout = st.button("Timeout Hidden", key="timeout_btn")
        
        st.components.v1.html(f"""
            <div style="font-family: sans-serif; display: flex; align-items: center; justify-content: space-between; background-color: #f0f2f6; padding: 10px 20px; border-radius: 8px; margin-bottom: 10px;">
                <span style="font-weight: bold; color: #31333F;">⏳ Temps restant pour cette question :</span>
                <span id="countdown_{i}" style="font-size: 20px; font-weight: bold; color: #ff4b4b;">{TEMPS_PAR_QUESTION}s</span>
            </div>
            <script>
                (function() {{
                    var timeLeft = {TEMPS_PAR_QUESTION};
                    var countdownElement = document.getElementById('countdown_{i}');
                    var timer = setInterval(function() {{
                        timeLeft--;
                        if (countdownElement) {{
                            countdownElement.textContent = timeLeft + "s";
                        }}
                        if (timeLeft <= 0) {{
                            clearInterval(timer);
                            window.parent.document.querySelector('button[key="timeout_btn"]').click();
                        }}
                    }}, 1000);
                }})();
            </script>
        """, height=60)

        st.markdown(f"### {q['question']}")

        rep_selectionnee = None
        if q["type"] == "simple":
            rep_selectionnee = st.radio("Choisissez une réponse :", q["options"], key=f"current_ans_{i}")
        else:
            selections = []
            for j, option in enumerate(q["options"]):
                if st.checkbox(option, key=f"check_{i}_{j}"):
                    selections.append(option)
            rep_selectionnee = selections
            st.session_state[f"current_ans_{i}"] = selections

        st.markdown("---")
        btn_valider = st.button("Valider et question suivante ➡")
        
        if btn_valider or bt_timeout:
            if bt_timeout:
                if q["type"] == "simple":
                    rep_selectionnee = st.session_state.get(f"current_ans_{i}", "")
                else:
                    rep_selectionnee = st.session_state.get(f"current_ans_{i}", [])
                
            passer_a_la_suivante(rep_selectionnee)

    # --- FIN ET SAUVEGARDE ---
    elif st.session_state.qcm_etape == "termine":
        score = 0
        reponses_utilisateur = st.session_state.reponses_utilisateur
        historique_reussite = {}
        mapping_final_sauvegarde = {}

        for i, q in enumerate(st.session_state.liste_questions):
            id_orig = str(q["id_original"])
            mapping_final_sauvegarde[id_orig] = reponses_utilisateur[i]
            
            if q["type"] == "simple":
                if reponses_utilisateur[i] == q["reponse"]:
                    score += 1
                    historique_reussite[id_orig] = 1.0
                else:
                    historique_reussite[id_orig] = 0.0
            else:
                bonnes = set(q["reponse"])
                choisies = set(reponses_utilisateur[i])
                score_question = len(bonnes.intersection(choisies)) / len(bonnes)
                mauvaises = choisies - bonnes
                score_question -= (len(mauvaises) * 0.25)
                score_question = max(0, score_question)
                score += score_question
                historique_reussite[id_orig] = round(score_question, 2)

        note = round(score / len(st.session_state.liste_questions) * 20, 2)

        # Sauvegarde sécurisée dans SQLite
        sauvegarder_resultat(
            lieu=st.session_state.lieu_utilisateur,
            nom=st.session_state.nom_utilisateur,
            score=round(score, 2),
            total=len(st.session_state.liste_questions),
            note=note,
            reponses_json=json.dumps(mapping_final_sauvegarde, ensure_ascii=False),
            details_json=json.dumps(historique_reussite)
        )

        st.success("🎉 Évaluation enregistrée avec succès !")
        st.metric("Votre note", f"{note}/20")
        
        if st.button("Quitter l'espace de test"):
            st.session_state.qcm_etape = "accueil"
            st.session_state.nom_utilisateur = ""
            st.session_state.lieu_utilisateur = ""
            st.rerun()

# ==================================
# CLASSEMENT & STATS (AVEC FILTRE DE LOT)
# ==================================
elif menu == "Classement":
    st.title("🏆 Tableau de Bord & Analyses")
    
    df = charger_tous_les_resultats()
    
    if not df.empty:
        # Filtre dynamique par Lot
        lieux_disponibles = sorted(df["lieu"].unique())
        lieu_filtre = st.selectbox("Sélectionner le LOT à analyser", ["Tous"] + lieux_disponibles)
        
        # Filtrage dynamique des données à afficher
        df_affiche = df if lieu_filtre == "Tous" else df[df["lieu"] == lieu_filtre]
        
        if not df_affiche.empty:
            # 1. Section Classement
            st.subheader(f"🥇 Classement Général — {lieu_filtre}")
            df_classement = df_affiche.sort_values(by="note", ascending=False).reset_index(drop=True)
            df_classement["Rang"] = df_classement.index + 1
            st.dataframe(
                df_classement[["Rang", "lieu", "nom", "score", "note"]], 
                column_config={"lieu": "LOT", "nom": "Nom"},
                use_container_width=True,
                hide_index=True
            )
            
            # Indicateurs globaux du groupe
            col1, col2, col3 = st.columns(3)
            col1.metric("Nombre total d'évalués", len(df_affiche))
            col2.metric("Moyenne générale", f"{round(df_affiche['note'].mean(), 2)} / 20")
            col3.metric("Note maximale obtenue", f"{round(df_affiche['note'].max(), 2)} / 20")
            
            # 2. Diagnostic analytique des compétences
            st.markdown("---")
            st.subheader("🎯 Diagnostic des Compétences (Analytique des questions)")
            
            if "details_reussite" in df_affiche.columns:
                analytics = {str(k): [] for k in range(len(questions))}
                for idx, row in df_affiche.dropna(subset=["details_reussite"]).iterrows():
                    try:
                        data_row = json.loads(row["details_reussite"])
                        for k, v in data_row.items():
                            if k in analytics: analytics[k].append(v)
                    except: pass
                
                rows_stats = []
                for k, liste_notes in analytics.items():
                    if liste_notes:
                        taux_reussite = (sum(liste_notes) / len(liste_notes)) * 100
                        taux_echec = 100 - taux_reussite
                        rows_stats.append({
                            "ID": int(k) + 1,
                            "Question": questions[int(k)]['question'],
                            "Taux de Réussite": round(taux_reussite, 1),
                            "Taux d'Échec": round(taux_echec, 1)
                        })
                
                if rows_stats:
                    df_analytics = pd.DataFrame(rows_stats)
                    df_difficiles = df_analytics[df_analytics["Taux d'Échec"] >= 50].sort_values(by="Taux d'Échec", ascending=False)
                    
                    if not df_difficiles.empty:
                        st.error(f"🚨 **Alertes pédagogiques : {len(df_difficiles)} notion(s) non assimilée(s) par plus de la moitié des élèves !**")
                        for _, r in df_difficiles.iterrows():
                            # Échappement propre pour éviter la SyntaxError des apostrophes
                            st.markdown(f"* **Question {r['ID']}** : *{r['Question']}*\n  * 🔴 **Taux d'échec : {r['Taux d\'Échec']}%** (Seulement {r['Taux de Réussite']}% de réussite)")
                    else:
                        st.success("✅ Félicitations ! Toutes les notions clés affichent un taux de réussite supérieur à 50% sur ce groupe.")
                    
                    st.markdown("#### 📋 Vue d'ensemble des taux d'assimilation")
                    df_visuel = df_analytics.sort_values(by="Taux d'Échec", ascending=False).reset_index(drop=True)
                    
                    st.dataframe(
                        df_visuel,
                        column_config={
                            "ID": st.column_config.NumberColumn("N°", width="small"),
                            "Question": st.column_config.TextColumn("Intitulé de la question", width="large"),
                            "Taux de Réussite": st.column_config.ProgressColumn("Taux de Réussite (%)", format="%f%%", min_value=0, max_value=100),
                            "Taux d'Échec": st.column_config.NumberColumn("Taux d'Échec (%)", format="%f%%")
                        },
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.warning("Aucun résultat enregistré pour ce LOT.")
    else:
        st.warning("Aucun résultat disponible pour générer les analyses.")

# ==================================
# DÉTAIL DES RÉPONSES (AVEC SÉLECTION PAR LOT PUIS ÉLÈVE)
# ==================================
elif menu == "Détail des réponses":
    st.title("📋 Réponses des participants")
    
    df = charger_tous_les_resultats()
    
    if not df.empty:
        # Premier niveau de filtre : Par LOT
        lieux_disponibles = sorted(df["lieu"].unique())
        lieu_filtre = st.selectbox("Filtrer par LOT", lieux_disponibles)
        
        df_groupe = df[df["lieu"] == lieu_filtre]
        
        if not df_groupe.empty:
            # Deuxième niveau : Les candidats du LOT choisi
            utilisateur = st.selectbox("Choisir un participant", df_groupe["nom"].tolist())
            ligne = df_groupe[df_groupe["nom"] == utilisateur].iloc[0]

            st.subheader(f"Feuille de notation de : {utilisateur} — {lieu_filtre} (Note globale : {ligne['note']}/20)")
            reponses_dict = json.loads(ligne["reponses"])
            
            for i, q in enumerate(questions):
                id_orig = str(i)
                st.markdown("---")
                st.markdown(f"### Question {i + 1} : {q['question']}")
                
                rep_donnee = reponses_dict.get(id_orig, None)
                
                est_correct = False
                if q["type"] == "simple":
                    est_correct = (rep_donnee == q["reponse"])
                else:
                    est_correct = (set(rep_donnee or []) == set(q["reponse"]))
                
                if rep_donnee is None or rep_donnee == "" or rep_donnee == []:
                    st.error("⚠️ Pas de réponse (Temps écoulé)")
                elif est_correct:
                    st.success(f"✔ **Réponse donnée :** {rep_donnee} — **Correct**")
                else:
                    st.error(f"✘ **Réponse donnée :** {rep_donnee} — **Incorrect**")
                
                st.info(f"💡 **Réponse attendue :** {q['reponse']}")
        else:
            st.warning("Aucun utilisateur enregistré dans ce LOT.")
    else:
        st.warning("Aucun résultat disponible.")