import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json
import io
from PIL import Image
from google import genai

# --- 1. CONFIGURACIÓN DE IDs ---
API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_ID = "1tVkG_cuKvJnsrIx5BPi-LN4kxEAYUKVuVd2uR92coaM"
FOLDER_ID = "1soUp4Ur99A699EQOknr6jkdk9YzuB1N6?hl=es"

# --- 2. CONEXIÓN A GOOGLE DRIVE Y SHEETS ---
@st.cache_resource
def conectar_google():
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    cred_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    creds = Credentials.from_service_account_info(cred_dict, scopes=SCOPES)
    gs = gspread.authorize(creds)
    drive = build('drive', 'v3', credentials=creds)
    return gs, drive

gs, drive_service = conectar_google()
hoja = gs.open_by_key(SHEET_ID).sheet1

@st.cache_data(show_spinner=False)
def descargar_imagen(file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        return request.execute()
    except Exception:
        return None

# --- 3. INTERFAZ DE LA APLICACIÓN ---
st.title("👕 Mi Clóset Digital ☁️")
st.write("¡Tu inventario ahora está sincronizado con tu Google Drive!")

tab_agregar, tab_galeria, tab_asesor = st.tabs(["➕ Agregar Prenda", "📸 Mi Galería", "🤖 Asesor de Estilo"])

# ==========================================
# PESTAÑA 1: AGREGAR PRENDA (AHORA A DRIVE)
# ==========================================
with tab_agregar:
    col1, col2 = st.columns(2)
    with col1:
        categoria = st.selectbox("¿Qué tipo de prenda es?", ["Playeras", "Camisas", "Playeras de fútbol", "Sudaderas", "Pantalones (Shorts/Pants)", "Calzado", "Calcetines", "Bóxers"])
        color_manual = st.text_input("Color de la prenda:", placeholder="Ej. Negro, Blanco...")
        estado = st.radio("Estado actual:", ["✨ Disponible", "🧺 En lavado / Sucia"])

    with col2:
        imagen = st.file_uploader("Sube la foto aquí", type=["jpg", "png", "jpeg"])

    if imagen is not None:
        st.image(imagen, width=250)
        
        if st.button("☁️ Subir a mi Drive y Guardar"):
            if not color_manual.strip():
                st.warning("⚠️ Escribe el color antes de guardar.")
            else:
                with st.spinner("Subiendo foto a Drive y registrando en Sheets..."):
                    # 1. Subir la foto a la carpeta de Drive
                    media = MediaIoBaseUpload(io.BytesIO(imagen.getvalue()), mimetype=imagen.type, resumable=True)
                    metadata = {'name': f"{categoria}_{color_manual}.jpg", 'parents': [FOLDER_ID]}
                    archivo_drive = drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
                    id_foto = archivo_drive.get('id')

                    # 2. Guardar los datos en el Excel
                    registros = hoja.get_all_records()
                    nuevo_id = 1 if not registros else max([int(r['id']) for r in registros if str(r['id']).isdigit()] + [0]) + 1
                    hoja.append_row([nuevo_id, categoria, estado, id_foto, color_manual])
                    
                    st.cache_data.clear() # Limpiar memoria para ver los cambios
                    st.success("¡Prenda guardada exitosamente en la nube!")

# ==========================================
# PESTAÑA 2: MI GALERÍA
# ==========================================
with tab_galeria:
    st.subheader("📚 Álbumes de tu Clóset")
    registros = hoja.get_all_records()
    
    if not registros:
        st.info("Aún no tienes prendas. ¡Agrega tu primera foto desde tu celular!")
    else:
        categorias_guardadas = list(set([str(r['categoria']) for r in registros]))
        album_sel = st.selectbox("📂 Elige una categoría:", categorias_guardadas)
        prendas_album = [r for r in registros if r['categoria'] == album_sel]
        
        cols = st.columns(3)
        for idx, prenda in enumerate(prendas_album):
            with cols[idx % 3]:
                img_bytes = descargar_imagen(prenda['ruta_imagen'])
                if img_bytes:
                    st.image(img_bytes, caption=f"{prenda['estado']} \n🎨 {prenda['color']}", use_container_width=True)
                
                c1, c2 = st.columns(2)
                with c1:
                    if prenda['estado'] == "✨ Disponible":
                        if st.button("🧼 Lavar", key=f"lavar_{prenda['id']}"):
                            celda = hoja.find(str(prenda['id']), in_column=1)
                            hoja.update_cell(celda.row, 3, "🧺 En lavado / Sucia")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        if st.button("✨ Limpia", key=f"limpia_{prenda['id']}"):
                            celda = hoja.find(str(prenda['id']), in_column=1)
                            hoja.update_cell(celda.row, 3, "✨ Disponible")
                            st.cache_data.clear()
                            st.rerun()
                with c2:
                    if st.button("🗑️ Borrar", key=f"del_{prenda['id']}"):
                        celda = hoja.find(str(prenda['id']), in_column=1)
                        hoja.delete_rows(celda.row)
                        st.cache_data.clear()
                        st.rerun()

# ==========================================
# PESTAÑA 3: ASESOR DE ESTILO (IA)
# ==========================================
with tab_asesor:
    st.subheader("🧠 Calificador de Outfits")
    ocasion = st.text_input("🎯 ¿A dónde vas?", placeholder="Ej. A clases, al gym, a una cita...")
    
    registros = hoja.get_all_records()
    ropa_limpia = [r for r in registros if r['estado'] == '✨ Disponible']
    
    if not ropa_limpia:
        st.warning("No tienes ropa limpia disponible.")
    else:
        st.write("👗 **Selecciona las prendas para tu outfit:**")
        seleccionadas = []
        imagenes_ia = []
        desc_ia = ""
        
        cols = st.columns(4)
        for idx, p in enumerate(ropa_limpia):
            with cols[idx % 4]:
                img_bytes = descargar_imagen(p['ruta_imagen'])
                if img_bytes:
                    st.image(img_bytes, use_container_width=True)
                    if st.checkbox("✔", key=f"chk_{p['id']}"):
                        seleccionadas.append(p)
                        imagenes_ia.append(Image.open(io.BytesIO(img_bytes)))
                        desc_ia += f"- {p['categoria']} (Color: {p['color']})\n"
                        
        st.divider()
        if st.button("✨ Calificar Outfit con IA") and seleccionadas:
            if not ocasion:
                st.error("Por favor, escribe a dónde vas.")
            else:
                with st.spinner("Gemini está analizando tu estilo..."):
                    try:
                        client = genai.Client(api_key=API_KEY)
                        prompt = f"Eres un asesor de moda. El usuario va a: '{ocasion}'. Prendas:\n{desc_ia}\nAnaliza el estilo y colores según las fotos adjuntas. Da una crítica honesta y constructiva."
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=[prompt] + imagenes_ia
                        )
                        st.success("¡Análisis completado!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Error con la IA: {e}")
