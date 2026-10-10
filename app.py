import streamlit as st
import sqlite3
import os
from PIL import Image
from google import genai

# --- ¡ATENCIÓN! PON TU API KEY AQUÍ ---
API_KEY = "GEMINI_API_KEY"

# --- 1. CONFIGURACIÓN DE LA BASE DE DATOS ---
def iniciar_base_datos():
    conn = sqlite3.connect("closet.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS prendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT,
            estado TEXT,
            ruta_imagen TEXT
        )
    ''')
    try:
        c.execute("ALTER TABLE prendas ADD COLUMN color TEXT")
    except sqlite3.OperationalError:
        pass 
    conn.commit()
    conn.close()

iniciar_base_datos()

if not os.path.exists("imagenes_guardadas"):
    os.makedirs("imagenes_guardadas")

# --- 2. ENCABEZADO DE LA APP ---
st.title("👕 Mi Clóset Digital")
st.write("¡Bienvenido al inventario inteligente de tu ropa!")

tab_agregar, tab_galeria, tab_asesor = st.tabs(["➕ Agregar Prenda", "📸 Mi Galería", "🤖 Asesor de Estilo"])

# ==========================================
# PESTAÑA 1: AGREGAR PRENDA
# ==========================================
with tab_agregar:
    col1, col2 = st.columns(2)

    with col1:
        categoria = st.selectbox("¿Qué tipo de prenda es?", ["Playeras", "Camisas", "Playeras de fútbol", "Sudaderas", "Pantalones (Shorts/Pants)", "Calzado", "Calcetines", "Bóxers"])
        color_manual = st.text_input("Color de la prenda:", placeholder="Ej. Negro, Blanco, Rojo...")
        estado = st.radio("Estado actual:", ["✨ Disponible", "🧺 En lavado / Sucia"])

    with col2:
        imagen = st.file_uploader("Sube la foto aquí", type=["jpg", "png", "jpeg"])

    if imagen is not None:
        st.image(imagen, caption=f"Prenda: {categoria} | Color: {color_manual}", width=300)
        
        if st.button("💾 Guardar Prenda en mi Clóset"):
            if color_manual.strip() == "":
                st.warning("⚠️ Por favor, escribe el color antes de guardar.")
            else:
                ruta_foto = os.path.join("imagenes_guardadas", imagen.name)
                with open(ruta_foto, "wb") as f:
                    f.write(imagen.getbuffer())
                
                conn = sqlite3.connect("closet.db")
                conn.execute("INSERT INTO prendas (categoria, estado, ruta_imagen, color) VALUES (?, ?, ?, ?)", (categoria, estado, ruta_foto, color_manual))
                conn.commit()
                conn.close()
                st.success("¡Prenda guardada con éxito!")

# ==========================================
# PESTAÑA 2: MI GALERÍA (AHORA CON BOTÓN BORRAR)
# ==========================================
with tab_galeria:
    st.subheader("📚 Álbumes de tu Clóset")
    
    conn = sqlite3.connect("closet.db")
    c = conn.cursor()
    c.execute("SELECT DISTINCT categoria FROM prendas")
    categorias_guardadas = [fila[0] for fila in c.fetchall()]
    
    if not categorias_guardadas:
        st.info("Aún no tienes prendas guardadas.")
    else:
        album_seleccionado = st.selectbox("📂 Elige una categoría:", categorias_guardadas)
        c.execute("SELECT id, ruta_imagen, estado, color FROM prendas WHERE categoria = ?", (album_seleccionado,))
        prendas_del_album = c.fetchall()
        
        columnas_galeria = st.columns(3)
        for indice, prenda in enumerate(prendas_del_album):
            id_prenda, ruta, estado_prenda, color_prenda = prenda[0], prenda[1], prenda[2], prenda[3] if len(prenda) > 3 else "No registrado"
            
            with columnas_galeria[indice % 3]:
                try:
                    st.image(ruta, caption=f"{estado_prenda} | 🎨 {color_prenda}", use_container_width=True)
                    
                    # Dividimos en dos columnas pequeñas para que quepan ambos botones
                    btn_col1, btn_col2 = st.columns(2)
                    
                    with btn_col1:
                        if estado_prenda == "✨ Disponible":
                            if st.button("🧼 Lavar", key=f"btn_{id_prenda}"):
                                conn_update = sqlite3.connect("closet.db")
                                conn_update.execute("UPDATE prendas SET estado = '🧺 En lavado / Sucia' WHERE id = ?", (id_prenda,))
                                conn_update.commit()
                                conn_update.close()
                                st.rerun()
                        else:
                            if st.button("✨ Limpia", key=f"btn_{id_prenda}"):
                                conn_update = sqlite3.connect("closet.db")
                                conn_update.execute("UPDATE prendas SET estado = '✨ Disponible' WHERE id = ?", (id_prenda,))
                                conn_update.commit()
                                conn_update.close()
                                st.rerun()
                    
                    with btn_col2:
                        if st.button("🗑️ Borrar", key=f"del_{id_prenda}"):
                            conn_update = sqlite3.connect("closet.db")
                            conn_update.execute("DELETE FROM prendas WHERE id = ?", (id_prenda,))
                            conn_update.commit()
                            conn_update.close()
                            st.rerun()
                            
                except Exception:
                    st.error("Error al cargar la imagen.")
    conn.close()

# ==========================================
# PESTAÑA 3: ASESOR DE ESTILO (VISUALMENTE LIMPIO)
# ==========================================
with tab_asesor:
    st.subheader("🧠 Calificador de Outfits")
    st.write("Selecciona la ropa que tienes limpia y dime a dónde vas. La IA te dará su opinión.")
    
    ocasion = st.text_input("🎯 ¿Cuál es la ocasión o a dónde vas?", placeholder="Ej. A clases, al gimnasio, a un concierto...")
    
    conn = sqlite3.connect("closet.db")
    c = conn.cursor()
    c.execute("SELECT id, categoria, color, ruta_imagen FROM prendas WHERE estado = '✨ Disponible'")
    ropa_limpia = c.fetchall()
    conn.close()
    
    if not ropa_limpia:
        st.warning("No tienes ropa limpia disponible en este momento.")
    else:
        st.write("👗 **Selecciona las prendas para tu outfit:**")
        prendas_seleccionadas = []
        imagenes_para_ia = []
        descripcion_para_ia = ""
        
        columnas_asesor = st.columns(4)
        for indice, prenda in enumerate(ropa_limpia):
            id_prenda, cat, col, ruta = prenda[0], prenda[1], prenda[2], prenda[3]
            with columnas_asesor[indice % 4]:
                try:
                    st.image(ruta, use_container_width=True)
                    # Cambiamos el texto largo por un simple "✔" para que se vea mucho más estético
                    if st.checkbox("✔", key=f"check_{id_prenda}"):
                        prendas_seleccionadas.append(prenda)
                        imagenes_para_ia.append(Image.open(ruta))
                        descripcion_para_ia += f"- {cat} (Color: {col})\n"
                except Exception:
                    pass
                    
        st.divider()
        
        if st.button("✨ Calificar mi Outfit con IA") and prendas_seleccionadas:
            if not ocasion:
                st.error("Por favor, escribe a dónde vas para poder calificar el outfit.")
            else:
                with st.spinner("Gemini está analizando la combinación de colores y texturas..."):
                    try:
                        client = genai.Client(api_key=API_KEY)
                        
                        prompt = f"""
                        Eres un experto asesor de moda y estilo. El usuario va a la siguiente ocasión: '{ocasion}'.
                        Ha seleccionado las siguientes prendas para su outfit:
                        {descripcion_para_ia}
                        
                        Te he adjuntado las fotos reales de las prendas. Analiza la combinación de colores, el contraste visual y si el estilo es adecuado para la ocasión.
                        Dame una valoración honesta, directa y con estilo. Si algo desentona, dilo y sugiere cómo mejorarlo.
                        """
                        
                        contenidos = [prompt] + imagenes_para_ia
                        
                        response = client.models.generate_content(
                            model='gemini-3.8-flash',
                            contents=contenidos
                        )
                        
                        st.success("¡Análisis completado!")
                        st.markdown(response.text)
                        
                    except Exception as e:
                        st.error(f"Hubo un error de conexión con la IA. Detalle: {e}")