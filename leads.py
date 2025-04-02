import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

# Configuration de la base de données
conn = sqlite3.connect('leads.db')
c = conn.cursor()

# Création table avec index pour les doublons
c.execute('''
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT,
    email TEXT UNIQUE,  -- Bloque les doublons d'emails
    telephone TEXT UNIQUE,  -- Bloque les doublons de téléphone
    status TEXT DEFAULT 'À appeler',
    notes TEXT,
    created_at DATETIME,
    last_contact DATETIME,
    contact_attempts INTEGER DEFAULT 0
)
''')
conn.commit()

# Interface Streamlit
st.set_page_config(page_title="Super Dashboard Leads", layout="wide")
st.title("🚀 Dashboard Avancé de Gestion des Leads")

# --------------------------------------
# Section 1 : Formulaire manuel anti-doublons
# --------------------------------------
with st.sidebar:
    st.header("Ajouter un lead manuellement")
    with st.form("form_lead"):
        nom = st.text_input("Nom")
        email = st.text_input("Email")
        telephone = st.text_input("Téléphone")
        submitted = st.form_submit_button("Ajouter")
        
        if submitted:
            # Vérification doublon
            existing_lead = c.execute('''
                SELECT * FROM leads 
                WHERE email = ? OR telephone = ?
            ''', (email, telephone)).fetchone()
            
            if existing_lead:
                st.error("Doublon détecté ! Ce email/téléphone existe déjà.")
            else:
                c.execute('''
                    INSERT INTO leads (nom, email, telephone, created_at)
                    VALUES (?, ?, ?, ?)
                ''', (nom, email, telephone, datetime.now()))
                conn.commit()
                st.success("Lead ajouté avec succès !")

# --------------------------------------
# Section 2 : Upload CSV avec vérification
# --------------------------------------
uploaded_file = st.file_uploader("Importer un CSV", type="csv")
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    
    # Nettoyage des données
    df['Téléphone'] = df['Téléphone'].astype(str).str.replace(r'\D', '', regex=True)
    
    # Anti-doublons
    existing_emails = pd.read_sql('SELECT email FROM leads', conn)['email'].tolist()
    existing_phones = pd.read_sql('SELECT telephone FROM leads', conn)['telephone'].tolist()
    
    df['is_duplicate'] = df.apply(lambda row: 
        row['Adresse e-mail'] in existing_emails or
        str(row['Téléphone']) in existing_phones, axis=1)
    
    duplicates = df[df['is_duplicate']]
    new_leads = df[~df['is_duplicate']]
    
    if not new_leads.empty:
        new_leads.to_sql('leads', conn, if_exists='append', index=False)
        st.success(f"{len(new_leads)} nouveaux leads ajoutés !")
    
    if not duplicates.empty:
        st.warning(f"{len(duplicates)} doublons ignorés :")
        st.dataframe(duplicates[['Nom', 'Adresse e-mail', 'Téléphone']])

# --------------------------------------
# Section 3 : Dashboard Avancé
# --------------------------------------
st.header("📊 Statistiques en Temps Réel")

# Charger les données
df_leads = pd.read_sql('''
    SELECT * FROM leads 
    ORDER BY created_at DESC 
    LIMIT 50  -- Derniers 50 leads
''', conn)

# KPI
total_leads = len(df_leads)
leads_a_appeler = len(df_leads[df_leads['status'] == "À appeler"])
taux_conversion = round((len(df_leads[df_leads['status'] == "Clos"]) / total_leads * 100), 1) if total_leads > 0 else 0
tentatives_moy = round(df_leads['contact_attempts'].mean(), 1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Leads", total_leads)
col2.metric("À Appeler", leads_a_appeler)
col3.metric("Taux Conversion (%)", f"{taux_conversion}%")
col4.metric("Tentatives Moy.", tentatives_moy)

# Graphiques
col1, col2 = st.columns(2)
with col1:
    st.subheader("Acquisition des Leads")
    df_daily = pd.read_sql('''
        SELECT DATE(created_at) as date, COUNT(*) as count 
        FROM leads 
        GROUP BY date
    ''', conn)
    fig = px.line(df_daily, x='date', y='count', title="Leads par Jour")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Répartition des Statuts")
    fig = px.pie(df_leads, names='status', title="Statuts des Leads")
    st.plotly_chart(fig, use_container_width=True)

# --------------------------------------
# Section 4 : Tableau des Derniers Leads
# --------------------------------------
st.header("📋 Derniers Leads Ajoutés")
edited_df = st.data_editor(
    df_leads,
    column_config={
        "status": st.column_config.SelectboxColumn(
            "Statut",
            options=["À appeler", "En attente", "Message envoyé", "Clos"],
            required=True
        ),
        "contact_attempts": st.column_config.NumberColumn(
            "Tentatives",
            min_value=0
        )
    },
    hide_index=True,
    key="editor"
)

# Sauvegarder modifications
if st.button("Mettre à jour les statuts"):
    edited_df.to_sql('leads', conn, if_exists='replace', index=False)
    st.rerun()

conn.close()