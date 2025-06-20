import streamlit as st
import pandas as pd
import numpy as np # Importamos numpy, es muy útil para condiciones
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
import io
import plotly.express as px
import plotly.graph_objects as go 
#========================================================================================
st.set_page_config(page_title="Dashboard Trazability TKI", layout="wide")
st.title("📊 Trazability TKI - ECHO")
#========================================================================================
# Autenticación con Google Sheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = service_account.Credentials.from_service_account_info(
    st.secrets, scopes=SCOPES
)
service = build("sheets", "v4", credentials=credentials)

# ID de la hoja y nombre de la hoja
SPREADSHEET_ID = "1AHWD_mg0X1G0uvuuPvNo0GcnndWe6toBMLs2cJ4usB4"
SHEET_NAME = "Echo" # changed pending

@st.cache_data(ttl=60) # actualiza cada 60 segundos
def load_data(): 
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2:AD100" # changed pending
    ).execute()

    values = result.get("values", [])
    if not values:
        st.warning("No se encontraron datos en la hoja de cálculo.")
        return pd.DataFrame()
    
    headers = values[0]
    data = values[1:]
    #return pd.DataFrame(data, columns=headers)
    # Rellenar filas cortas con valores vacíos para que coincidan con headers
    fixed_data = [row + [""] * (len(headers) - len(row)) for row in data]

    return pd.DataFrame(fixed_data, columns=headers)
#========================================================================================
# Cargar datos
df = load_data()

# --- PASO 1: Renombrar las columnas para que sean más fáciles de usar ---
df.rename(columns={
    '#': 'ID',
    'MAC': 'MAC',
    'BATCH': 'BATCH',
    'LAB TESTING DATE': 'Date_Test_Lab',
    'Testing_Date01': 'Date_NMEA_QC1',
    'Testing_Date02': 'Date_NMEA_QC2',
    'Production Date': 'Date_Prod',
    'Shippent Date': 'Date_Shipp' 
}, inplace=True)

# --- PASO 2: Eliminar filas donde la MAC es nula o vacía, ya que no representan un equipo válido.
df.dropna(subset=['MAC'], inplace=True)
df = df[df['MAC'].str.strip() != '']
df['MAC'] = df['MAC'].astype(str).str.strip()

# --- PASO 3: Convertir las columnas de fecha a formato de fecha ---

#df['Date_Test_Lab'] = pd.to_datetime(df['Date_Test_Lab'], format='%d/%m/%Y', errors='coerce')
#df['Date_NMEA_QC1'] = pd.to_datetime(df['Date_NMEA_QC1'], format='%d-%m-%y', errors='coerce')
#df['Date_NMEA_QC2'] = pd.to_datetime(df['Date_NMEA_QC2'], format='%d-%m-%y', errors='coerce')
#df['Date_Prod'] = pd.to_datetime(df['Date_Prod'], format='%d-%m-%y', errors='coerce')
#df['Date_Shipp'] = pd.to_datetime(df['Date_Shipp'], format='%d-%m-%y', errors='coerce')

df['Date_Test_Lab'] = pd.to_datetime(df['Date_Test_Lab'], errors='coerce', dayfirst=True)
df['Date_NMEA_QC1'] = pd.to_datetime(df['Date_NMEA_QC1'], errors='coerce', dayfirst=True)
df['Date_NMEA_QC2'] = pd.to_datetime(df['Date_NMEA_QC2'], errors='coerce', dayfirst=True)
df['Date_Prod'] = pd.to_datetime(df['Date_Prod'], errors='coerce', dayfirst=True)
df['Date_Shipp'] = pd.to_datetime(df['Date_Shipp'], errors='coerce', dayfirst=True)


# --- PASO 4: Asignamos la etapa de forma secuencial. La última condición que se cumpla será la etapa final.
df['Etapa_Actual'] = '0. Pendiente' # Valor por defecto
df.loc[df['Date_Test_Lab'].notna(), 'Etapa_Actual'] = '1. Pruebas de Laboratorio'
df.loc[df['Date_NMEA_QC1'].notna(), 'Etapa_Actual'] = '2. NMEA QC 01'
df.loc[df['Date_NMEA_QC2'].notna(), 'Etapa_Actual'] = '3. NMEA QC 02'
df.loc[df['Date_Prod'].notna(), 'Etapa_Actual'] = '4. Produccion Finalizada'
df.loc[df['Date_Shipp'].notna(), 'Etapa_Actual'] = '5. Equipos Enviados'

# --- PASO 5: Calcular la duración en días entre cada etapa ---
df['Dias_Lab_a_NMEA1'] = (df['Date_NMEA_QC1'] - df['Date_Test_Lab']).dt.days
df['Dias_NMEA1_a_NMEA2'] = (df['Date_NMEA_QC2'] - df['Date_NMEA_QC1']).dt.days
df['Dias_NMEA2_a_FinProd'] = (df['Date_Prod'] - df['Date_NMEA_QC2']).dt.days
df['Dias_Prod_Shipp'] = (df['Date_Prod'] - df['Date_Shipp']).dt.days
df['Dias_Totales'] = (df['Date_Shipp'] - df['Date_Test_Lab']).dt.days
#========================================================================================
# --- KPIs / Resumen General ---
st.header("Resumen General del Proceso")

# Contar equipos en cada etapa (considerando la última completada)
total_equipos = len(df)
en_etapa1 = len(df[df['Etapa_Actual'] == '1. Pruebas de Laboratorio'])
en_etapa2 = len(df[df['Etapa_Actual'] == '2. NMEA QC 01'])
en_etapa3 = len(df[df['Etapa_Actual'] == '3. NMEA QC 02'])
en_etapa4 = len(df[df['Etapa_Actual'] == '4. Produccion Finalizada'])
en_etapa5 = len(df[df['Etapa_Actual'] == '5. Equipos Enviados'])

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total de Equipos", f"{total_equipos}")
col2.metric("En Lab Test", f"{en_etapa1}")
col3.metric("En NMEA QC 1", f"{en_etapa2}")
col4.metric("En NMEA QC 2", f"{en_etapa3}")
col5.metric("Produccion finalizada", f"{en_etapa4}")
col6.metric("Enviados", f"{en_etapa5}")

# --- Análisis de Tiempos ---
st.header("⏱️ Análisis de Tiempos de Procesamiento")
col1_tiempo, col2_tiempo = st.columns(2)

with col1_tiempo:
    st.subheader("Tiempos Promedio entre Etapas")
    avg_dias_1_2 = df['Dias_Lab_a_NMEA1'].mean()
    avg_dias_2_3 = df['Dias_NMEA1_a_NMEA2'].mean()
    avg_dias_3_4 = df['Dias_NMEA2_a_FinProd'].mean()
    avg_dias_4_5 = df['Dias_Prod_Shipp'].mean()
    avg_dias_total = df['Dias_Totales'].mean()

    # Mostramos los promedios solo si se pueden calcular (si hay datos)
    if pd.notna(avg_dias_1_2):
        st.info(f"**Promedio Lab → NMEA 1:** {avg_dias_1_2:.1f} días")
    if pd.notna(avg_dias_2_3):
        st.info(f"**Promedio NMEA 1 → NMEA 2:** {avg_dias_2_3:.1f} días")
    if pd.notna(avg_dias_3_4):
        st.info(f"**Promedio NMEA 2 → Produccion Final:** {avg_dias_3_4:.1f} días")
    if pd.notna(avg_dias_4_5):
        st.info(f"**Produccion Final → Envio:** {avg_dias_4_5:.1f} días")
    if pd.notna(avg_dias_total):
        st.success(f"**Promedio Total Proceso:** {avg_dias_total:.1f} días")
        
with col2_tiempo:
    st.subheader("Cantidad de Equipos por Etapa")
    # Crear gráfico de pastel (porcentaje de equipos por etapa)
    etapas = [
        '1. Pruebas de Laboratorio',
        '2. NMEA QC 01',
        '3. NMEA QC 02',
        '4. Produccion Finalizada',
        '5. Equipos Enviados'
    ]
    colores = ['#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c']

    valores = [len(df[df['Etapa_Actual'] == etapa]) for etapa in etapas]

    fig = go.Figure(go.Pie(
        labels=etapas,
        values=valores,
        hole=0.4,
        marker_colors=colores,
        #textinfo='percent+label',
        insidetextorientation='radial',
        pull=[0.05] * len(etapas)
    ))
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)


# --- Detalle por Etapa ---
st.header("📋 Estado de los Equipos por Etapa")

# Crear pestañas para cada etapa
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"Lab Test ({en_etapa1})", 
    f"NMEA QC 01 ({en_etapa2})", 
    f"NMEA QC 02 ({en_etapa3})",
    f" Producciòn Final ({en_etapa4})",
    f" Equipos Enviados ({en_etapa5})"
])

with tab1:

    st.subheader("Equipos en Pruebas de Laboratorio")
    df_filtrado = df[df['Etapa_Actual'] == '1. Pruebas de Laboratorio']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Test_Lab']])

with tab2:
    st.subheader("Equipos en Evaluación NMEA QC 01")
    df_filtrado = df[df['Etapa_Actual'] == '2. NMEA QC 01']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_NMEA_QC1', 'Dias_Lab_a_NMEA1']])

with tab3:
    st.subheader("Equipos en Evaluación NMEA QC 02")
    df_filtrado = df[df['Etapa_Actual'] == '3. NMEA QC 02']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_NMEA_QC2', 'Dias_NMEA1_a_NMEA2']])

with tab4:
    st.subheader("Equipos en Producciòn Finalizada")
    df_filtrado = df[df['Etapa_Actual'] == '4. Produccion Finalizada']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Prod', 'Dias_Totales']])

with tab5:
    st.subheader("Equipos Enviados")
    df_filtrado = df[df['Etapa_Actual'] == '5. Equipos Enviados']
    st.dataframe(df_filtrado[['ID', 'MAC', 'BATCH', 'Date_Prod', 'Dias_Totales']])

# --- Tabla de Datos Completa ---
with st.expander("Ver tabla de datos completa y procesada"):
    st.write("Esta tabla contiene todos los datos cargados y las columnas calculadas (etapas y duraciones).")
    st.dataframe(df)

