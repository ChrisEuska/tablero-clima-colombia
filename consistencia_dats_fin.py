import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os
import glob
import io

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="Depuración y Estacionalidad", layout="wide")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    h1, h2, h3 {color: #2c3e50;}
    
    .card-base {
        background-color: white; 
        padding: 15px; 
        border-radius: 8px; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        text-align: center;
        margin-bottom: 15px;
    }
    .card-title { font-size: 11px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; margin-bottom: 5px;}
    .card-value { font-size: 20px; font-weight: bold; color: #2c3e50; }
    .card-subtext { font-size: 11px; color: #e74c3c; font-weight: bold; margin-top: 5px;}
    
    .title-red { color: #c0392b !important; font-size: 1.5rem; font-weight: bold;}
    .title-normal { color: #2c3e50 !important; font-size: 1.5rem; font-weight: bold;}
    
    .stat-box { background-color: #f8f9fa; border-left: 4px solid #34495e; padding: 10px; border-radius: 4px; margin-bottom: 10px; }
    .stat-label { font-size: 12px; color: #7f8c8d; font-weight: bold; }
    .stat-val { font-size: 16px; color: #2c3e50; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. CARGA DE BASE DE DATOS YA PROCESADA (EN PARTES PARA LA WEB)
# ==========================================
ARCHIVO_CONSISTENCIA = "Consistencia_Homogeneidad_Estaciones.xlsx"

@st.cache_data(show_spinner="Cargando Base de Datos Maestra... (Tomará unos segundos)")
def cargar_entorno_produccion():
    # 1. Cargar el catálogo original
    archivos_cat = glob.glob("*Catalogo*IDEAM*")
    df_cat = pd.DataFrame()
    if archivos_cat:
        archivo = archivos_cat[0]
        if archivo.endswith(('.xls', '.xlsx')): df_cat = pd.read_excel(archivo)
        else:
            try: df_cat = pd.read_csv(archivo, sep=',', encoding='latin-1')
            except: df_cat = pd.read_csv(archivo, sep=';', encoding='latin-1')
        df_cat.columns = df_cat.columns.str.strip().str.upper()
        df_cat['CODIGO'] = df_cat['CODIGO'].astype(str).str.replace('.0', '', regex=False)

    # 2. Cargar las estadísticas de depuración
    df_consistencia = pd.read_excel(ARCHIVO_CONSISTENCIA)
    df_consistencia['CODIGO'] = df_consistencia['CODIGO'].astype(str)
    
    # Cruzar catálogo con estadísticas
    df_cat_definitivo = pd.merge(df_cat, df_consistencia, on='CODIGO', how='inner')

    # 3. Leer y unir los pedacitos de Parquet
    archivos_parquet = sorted(glob.glob("Series_Ajustadas_parte_*.parquet"))
    lista_dfs = [pd.read_parquet(archivo) for archivo in archivos_parquet]
    df_datos_limpios = pd.concat(lista_dfs, ignore_index=True)

    return df_cat_definitivo, df_datos_limpios

# ==========================================
# 3. CONTROL DE FLUJO DE LA APLICACIÓN
# ==========================================
st.title("📊 Análisis Estadístico y Estacionalidad")

# Verificar si el archivo de consistencia y al menos una parte del Parquet existen
partes_parquet = glob.glob("Series_Ajustadas_parte_*.parquet")

if not partes_parquet or not os.path.exists(ARCHIVO_CONSISTENCIA):
    st.error("⚠️ **No se encontraron las particiones de la Base de Datos Maestra.**")
    st.info("Asegúrate de que los archivos 'Series_Ajustadas_parte_X.parquet' estén en la misma carpeta junto con el código y los Excels.")
    st.stop()

# Si existen, se cargan a memoria (solo ocurre una vez al abrir la app)
try:
    df_cat_def, df_datos = cargar_entorno_produccion()
except Exception as e:
    st.error(f"Error leyendo los archivos maestros: {e}")
    st.stop()

# ==========================================
# 4. MENÚ LATERAL Y SELECCIÓN (INTERACCIÓN INSTANTÁNEA)
# ==========================================
with st.sidebar:
    st.header("🔍 Seleccionar Estación")
    st.caption("⚡ Modo Producción Web Activado")
    deptos = sorted(df_cat_def['DEPARTAMENTO'].astype(str).unique())
    sel_depto = st.selectbox("1. Departamento:", deptos)
    
    df_muni = df_cat_def[df_cat_def['DEPARTAMENTO'] == sel_depto]
    munis = sorted(df_muni['MUNICIPIO'].astype(str).unique())
    sel_muni = st.selectbox("2. Municipio:", munis)
    
    df_est_cat = df_muni[df_muni['MUNICIPIO'] == sel_muni].copy()
    df_est_cat['ETIQUETA'] = df_est_cat['NOMBRE'] + " [" + df_est_cat['CODIGO'] + "]"
    sel_estacion = st.selectbox("3. Estación:", df_est_cat['ETIQUETA'].tolist())
    
    info_est = df_est_cat[df_est_cat['ETIQUETA'] == sel_estacion].iloc[0]
    codigo_seleccionado = info_est['CODIGO']
    nombre_estacion = info_est['NOMBRE']

# ==========================================
# 5. ANÁLISIS ESTADÍSTICO DE LOS DATOS
# ==========================================
st.subheader(f"📈 Análisis Estadístico de Precipitación ({nombre_estacion})")
st.markdown("Resultados de la validación matemática, depuración y homogeneidad aplicados a la serie histórica.")

e1, e2, e3, e4, e5 = st.columns(5)
def build_stat_box(label, value): return f'<div class="stat-box"><div class="stat-label">{label}</div><div class="stat-val">{value}</div></div>'

e1.markdown(build_stat_box("Nivel Consistencia", info_est.get('Consistencia','N/A')), unsafe_allow_html=True)
e2.markdown(build_stat_box("R² Doble Masa", info_est.get('R2_DobleMasa','N/A')), unsafe_allow_html=True)
e3.markdown(build_stat_box("Coef. Variación (CV)", info_est.get('CV','N/A')), unsafe_allow_html=True)
e4.markdown(build_stat_box("Vacíos Originales", f"{info_est.get('Vacios_Originales_1991_2024_%', 0)} %"), unsafe_allow_html=True)
e5.markdown(build_stat_box("Ajuste Serie", "Aplicado" if info_est.get('Ajuste_DobleMasa')=='Sí' else "No Requerido"), unsafe_allow_html=True)

st.markdown(f"**Método de Relleno Utilizado:** `{info_est.get('Metodo_Llenado', 'Desconocido')}`")
st.markdown("---")

# ==========================================
# 6. DESCARGA INDIVIDUAL DE LA ESTACIÓN
# ==========================================
st.subheader("📥 Exportar Serie Diaria Ajustada")
st.markdown("Descarga la tabla de datos de **esta estación específica**. (La columna 'Es_Relleno' marca True si el dato es sintético).")

@st.cache_data(show_spinner=False)
def generar_excel_individual(codigo):
    df_1991_2024 = df_datos[df_datos['CODIGO'] == codigo].copy()
    df_export = df_1991_2024[['Fecha', 'Valor', 'Es_Relleno']].copy()
    df_export['Fecha'] = df_export['Fecha'].dt.strftime('%Y-%m-%d')
    df_export['Valor'] = df_export['Valor'].round(2)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Serie_1991_2024')
    return output.getvalue()

if codigo_seleccionado:
    excel_data = generar_excel_individual(codigo_seleccionado)
    st.download_button(
        label=f"⬇️ Descargar Datos ({nombre_estacion})",
        data=excel_data,
        file_name=f"Serie_Ajustada_{codigo_seleccionado}_1991_2024.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.markdown("---")

# ==========================================
# 7. ESTACIONALIDAD Y EXTREMOS HISTÓRICOS
# ==========================================
if codigo_seleccionado:
    df_est_datos = df_datos[df_datos['CODIGO'] == codigo_seleccionado].copy()
    df_est_datos['Año'] = df_est_datos['Fecha'].dt.year
    df_est_datos['Mes'] = df_est_datos['Fecha'].dt.month

    min_y, max_y = df_est_datos['Año'].min(), df_est_datos['Año'].max()

    c_titulo, c_slider = st.columns([1, 1])
    with c_slider:
        rango_anios = st.slider(
            "Modificar Periodo Climatológico:", 
            min_value=int(min_y), max_value=int(max_y), 
            value=(int(max(min_y, 1991)), int(min(max_y, 2020)))
        )

    df_periodo = df_est_datos[(df_est_datos['Año'] >= rango_anios[0]) & (df_est_datos['Año'] <= rango_anios[1])].copy()

    anios_con_datos = df_periodo['Año'].unique()
    rango_esperado = list(range(1991, 2021))
    cumple_periodo = (rango_anios == (1991, 2020)) and all(y in anios_con_datos for y in rango_esperado)

    mensual_por_ano = df_periodo.groupby(['Año', 'Mes'])['Valor'].sum().reset_index()
    
    climatologia = mensual_por_ano.groupby('Mes').agg(
        Promedio=('Valor', 'mean'), Maximo=('Valor', 'max'), Minimo=('Valor', 'min')
    ).reset_index().round(1)
    
    nombres_meses = {1:'Enero', 2:'Febrero', 3:'Marzo', 4:'Abril', 5:'Mayo', 6:'Junio', 7:'Julio', 8:'Agosto', 9:'Septiembre', 10:'Octubre', 11:'Noviembre', 12:'Diciembre'}
    climatologia['Mes_Nombre'] = climatologia['Mes'].map(nombres_meses)

    col_grafica, col_metricas = st.columns([3, 1])

    with col_grafica:
        titulo_texto = f"Estacionalidad de Lluvias: {nombre_estacion} <br><span style='font-size:18px; color:#7f8c8d;'>{sel_muni}, {sel_depto}</span>"
        if cumple_periodo:
            st.markdown(f"<div class='title-normal'>{titulo_texto} (1991-2020)</div>", unsafe_allow_html=True)
            st.caption("✔️ Serie con normal climatológica completa.")
        else:
            st.markdown(f"<div class='title-red'>{titulo_texto} ({rango_anios[0]}-{rango_anios[1]})</div>", unsafe_allow_html=True)
            st.caption("⚠️ **Atención:** Periodo fuera de la normal estándar 1991-2020 o con años faltantes en el rango.")

        fig = go.Figure()
        
        # Textos redondeados a enteros para la visualización gráfica
        texto_promedio = ["<b>" + str(int(round(val, 0))) + "</b>" for val in climatologia['Promedio']]
        texto_maximo = [str(int(round(val, 0))) for val in climatologia['Maximo']]
        texto_minimo = [str(int(round(val, 0))) for val in climatologia['Minimo']]

        fig.add_trace(go.Bar(
            name='Promedio Mensual', x=climatologia['Mes_Nombre'], y=climatologia['Promedio'],
            marker_color='#3498db', text=texto_promedio, textposition='inside', textfont=dict(color='white', size=15)
        ))
        
        # Máximos en AZUL OSCURO (#1A5276)
        fig.add_trace(go.Scatter(
            name='Máx. Mensual Histórico', x=climatologia['Mes_Nombre'], y=climatologia['Maximo'],
            mode='markers+text', marker=dict(color='#1A5276', symbol='triangle-up', size=10),
            text=texto_maximo, textposition='top center', textfont=dict(color='#1A5276', size=11, family="Arial Black")
        ))
        
        # Mínimos en ROJO (#c0392b)
        fig.add_trace(go.Scatter(
            name='Mín. Mensual Histórico', x=climatologia['Mes_Nombre'], y=climatologia['Minimo'],
            mode='markers+text', marker=dict(color='#c0392b', symbol='triangle-down', size=10),
            text=texto_minimo, textposition='bottom center', textfont=dict(color='#c0392b', size=11, family="Arial Black")
        ))

        fig.update_layout(
            barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis_title="<b>Precipitación (mm)</b>", xaxis_title="", margin=dict(t=10, b=0, l=0, r=0), height=450,
            font=dict(color='black')
        )
        
        fig.update_xaxes(tickfont=dict(color='black', size=12, family="Arial Black"), title_font=dict(color='black'))
        fig.update_yaxes(tickfont=dict(color='black', size=12, family="Arial Black"), title_font=dict(color='black', size=14, family="Arial Black"))
        
        st.plotly_chart(fig, use_container_width=True)

    with col_metricas:
        st.markdown("<br>", unsafe_allow_html=True)
        idx_max_diario = df_periodo['Valor'].idxmax()
        val_max_diario = df_periodo.loc[idx_max_diario, 'Valor']
        fecha_max_diario = df_periodo.loc[idx_max_diario, 'Fecha'].strftime('%Y-%m-%d')
        
        idx_max_mensual = mensual_por_ano['Valor'].idxmax()
        val_max_mensual = mensual_por_ano.loc[idx_max_mensual, 'Valor']
        anio_max_men = int(mensual_por_ano.loc[idx_max_mensual, 'Año'])
        mes_max_men = nombres_meses[int(mensual_por_ano.loc[idx_max_mensual, 'Mes'])]
        
        mes_lluvioso = climatologia.loc[climatologia['Promedio'].idxmax()]['Mes_Nombre']
        mes_seco = climatologia.loc[climatologia['Promedio'].idxmin()]['Mes_Nombre']

        st.markdown(f"""
        <div class="card-base" style="border-left: 5px solid #c0392b;">
            <div class="card-title">☔ Máximo Histórico en 24h</div>
            <div class="card-value">{val_max_diario:.1f} mm</div>
            <div class="card-subtext">📅 Fecha: {fecha_max_diario}</div>
        </div>
        <div class="card-base" style="border-left: 5px solid #8e44ad;">
            <div class="card-title">🌊 Máximo Mensual Histórico</div>
            <div class="card-value">{val_max_mensual:.1f} mm</div>
            <div class="card-subtext">📅 Mes: {mes_max_men} {anio_max_men}</div>
        </div>
        <div class="card-base" style="border-left: 5px solid #2980b9;">
            <div class="card-title">☁️ Régimen Lluvioso</div>
            <div class="card-value">Mes {mes_lluvioso}</div>
        </div>
        <div class="card-base" style="border-left: 5px solid #f1c40f;">
            <div class="card-title">☀️ Régimen Seco</div>
            <div class="card-value">Mes {mes_seco}</div>
        </div>
        """, unsafe_allow_html=True)