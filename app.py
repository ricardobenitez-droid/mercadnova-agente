from __future__ import annotations
import os
import re
from pathlib import Path
import gradio as gr
from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

# ==========================================
# 1. CONFIGURACIÓN INICIAL (RENDER & LOCAL)
# ==========================================
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()
PDF_PATH = Path(os.getenv("PDF_PATH", str(BASE_DIR / "data" / "Documentacion_MercaNova_Ecommerce.pdf")))
PORT = int(os.getenv("PORT", "10000"))

if not GEMINI_API_KEY:
    raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")
if not GEMINI_MODEL:
    raise RuntimeError("Falta la variable de entorno GEMINI_MODEL.")
if not PDF_PATH.exists():
    raise FileNotFoundError(f"No se encontró el PDF: {PDF_PATH}")

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. PROCESAMIENTO DEL PDF Y BM25
# ==========================================
def normalizar_texto(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()

def dividir_texto(texto: str, pagina: int, tamano: int = 1000, solapamiento: int = 150) -> list[dict]:
    texto = normalizar_texto(texto)
    fragmentos = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + tamano, len(texto))
        if fin < len(texto):
            corte = texto.rfind(". ", inicio, fin)
            if corte > inicio + tamano // 2:
                fin = corte + 1
        contenido = texto[inicio:fin].strip()
        if contenido:
            fragmentos.append({"page": pagina, "text": contenido})
        if fin >= len(texto):
            break
        inicio = max(fin - solapamiento, inicio + 1)
    return fragmentos

def cargar_documento(ruta_pdf: Path) -> tuple[list[dict], int]:
    lector = PdfReader(str(ruta_pdf))
    fragmentos = []
    for numero, pagina in enumerate(lector.pages, start=1):
        texto = pagina.extract_text() or ""
        fragmentos.extend(dividir_texto(texto=texto, pagina=numero))
    if not fragmentos:
        raise RuntimeError("El PDF no contiene texto extraíble.")
    return fragmentos, len(lector.pages)

FRAGMENTOS, TOTAL_PAGINAS = cargar_documento(PDF_PATH)

def tokenizar(texto: str) -> list[str]:
    texto = texto.lower()
    tildes = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
    for con_tilde, sin_tilde in tildes.items():
        texto = texto.replace(con_tilde, sin_tilde)
        
    palabras = re.findall(r"[a-zñ0-9]+", texto)
    tokens = []
    
    sinonimos = {
        "precio": ["tarifa", "costo", "valor", "monto"],
        "precios": ["tarifas", "costos", "valores", "montos"],
        "envio": ["entrega", "despacho", "transporte"],
        "envios": ["entregas", "despachos", "transporte"],
        "devolver": ["devolucion", "reembolso", "retorno"],
        "devoluciones": ["reembolsos", "retornos"]
    }
    
    for p in palabras:
        tokens.append(p)
        singular = p
        if p.endswith('s') and len(p) > 3:
            singular = p[:-1]
            tokens.append(singular)
        if p.endswith('es') and len(p) > 4:
            singular = p[:-2]
            tokens.append(singular)
            
        if p in sinonimos:
            tokens.extend(sinonimos[p])
        if singular in sinonimos and singular != p:
            tokens.extend(sinonimos[singular])
            
    return tokens

CORPUS_TOKENIZADO = [tokenizar(fragmento["text"]) for fragmento in FRAGMENTOS]
BM25 = BM25Okapi(CORPUS_TOKENIZADO)

def recuperar_fragmentos(pregunta: str, cantidad: int = 5) -> list[dict]:
    tokens = tokenizar(pregunta)
    puntajes = BM25.get_scores(tokens)
    indices = sorted(range(len(puntajes)), key=lambda indice: puntajes[indice], reverse=True)[:cantidad]
    return [FRAGMENTOS[indice] for indice in indices]

# ==========================================
# 3. LÓGICA DEL AGENTE
# ==========================================
def formatear_historial(historial, limite: int = 6) -> str:
    if not historial:
        return "Sin conversación anterior."
    lineas = []
    for mensaje in historial[-limite:]:
        if not isinstance(mensaje, dict):
            continue
        rol = mensaje.get("role", "")
        contenido = mensaje.get("content", "")
        if isinstance(contenido, str):
            nombre = "Usuario" if rol == "user" else "Asistente"
            lineas.append(f"{nombre}: {contenido}")
    return "\n".join(lineas) if lineas else "Sin conversación anterior."

def responder_ecommerce(pregunta, historial=None):
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return "Escribí una pregunta sobre la tienda."
        
    documentos = recuperar_fragmentos(pregunta, cantidad=5)
    bloques = []
    paginas_usadas = []
    for documento in documentos:
        pagina = documento["page"]
        paginas_usadas.append(pagina)
        bloques.append(f"[Página {pagina}]\n{documento['text']}")
        
    contexto = "\n\n---\n\n".join(bloques)
    historial_texto = formatear_historial(historial)
    paginas_ordenadas = sorted(set(paginas_usadas))
    
    prompt = f"""
Sos NovaBot, el asistente documental de MercaNova,
una tienda e-commerce ficticia creada para el
Challenge Alura Agente.
REGLAS OBLIGATORIAS:
Respondé en español claro.
Utilizá únicamente el CONTEXTO DOCUMENTAL.
No inventes precios, plazos, políticas, productos,
 teléfonos, correos ni procedimientos.

Mantené exactamente los montos y condiciones.
Si la respuesta no está en el contexto, respondé:
 "No encontré esa información en la documentación
 disponible de MercaNova."

No afirmes que MercaNova es una empresa real.
Finalizá indicando las páginas consultadas.
HISTORIAL RECIENTE:
{historial_texto}
CONTEXTO DOCUMENTAL:
{contexto}
PREGUNTA:
{pregunta}
Redactá la respuesta:
""".strip()

    try:
        resultado = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        respuesta = (resultado.text or "").strip()
    except Exception as error:
        return f"No pude consultar Gemini. Detalle técnico: {type(error).__name__}: {error}"

    if not respuesta:
        respuesta = "No encontré esa información en la documentación disponible de MercaNova."

    if "fuentes consultadas" not in respuesta.lower():
        paginas_texto = ", ".join(str(pagina) for pagina in paginas_ordenadas)
        respuesta += f"\n\n**Fuentes consultadas:** páginas {paginas_texto}."
    return respuesta

MENSAJE_BIENVENIDA = (
    "¡Hola! Soy **NovaBot** 🛍️\n\n"
    "Puedo ayudarte con envíos, pagos, devoluciones, "
    "garantías, pedidos y políticas de MercaNova.\n\n"
    "¿Qué necesitás consultar?"
)

def historial_inicial():
    return [{"role": "assistant", "content": MENSAJE_BIENVENIDA}]

def enviar_mensaje(mensaje, historial):
    mensaje = (mensaje or "").strip()
    historial = historial or historial_inicial()
    if not mensaje:
        return "", historial
        
    respuesta = responder_ecommerce(mensaje, historial)
    nuevo_historial = historial + [
        {"role": "user", "content": mensaje},
        {"role": "assistant", "content": respuesta}
    ]
    return "", nuevo_historial

def limpiar_chat():
    return historial_inicial(), ""

consultas = [
    ("Envíos 🚚", "¿Cuánto cuesta el envío a Nacional o Internacional?"),
    ("Devoluciones 🔄", "¿Cuántos días tengo para devolver un producto?"),
    ("Pagos 💳", "¿Qué métodos de pago acepta la tienda?"),
    ("Garantías 🛡️", "¿Qué cubre la garantía?"),
    ("Seguimiento 📍", "¿Cómo puedo rastrear mi pedido?"),
    ("Cancelaciones ❌", "¿Puedo cancelar un pedido ya confirmado?")
]

# ==========================================
# 4. INTERFAZ GRÁFICA (TEMA, CSS Y BLOQUES)
# ==========================================
tema = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="violet",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
)

css = """
html, body {
    background-color: #F3F4F6 !important;
    overflow-x: hidden !important;
}
.gradio-container {
    max-width: 1000px !important;
    margin: 0 auto !important;
    padding: 30px 20px !important;
    background: transparent !important;
    border: none !important;
}
#header {
    padding: 30px;
    margin-bottom: 24px;
    border-radius: 16px;
    color: white;
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
    box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
}
.badge-container {
    margin-top: 16px;
    display: flex;
    gap: 12px;
    font-size: 0.85rem;
    flex-wrap: wrap;
}
.badge {
    background: rgba(255, 255, 255, 0.2);
    padding: 6px 12px;
    border-radius: 20px;
    backdrop-filter: blur(4px);
    font-weight: 500;
    letter-spacing: 0.3px;
}
#chat-panel {
    background: #FFFFFF !important;
    border-radius: 16px !important;
    padding: 24px !important;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01) !important;
    border: 1px solid #E5E7EB !important;
}
.quick-button {
    background: #F9FAFB !important;
    border: 1px solid #E5E7EB !important;
    color: #4B5563 !important;
    border-radius: 12px !important;
    min-height: 48px !important;
    font-weight: 500 !important;
    transition: all 0.2s ease-in-out !important;
}
.quick-button:hover {
    border-color: #4F46E5 !important;
    color: #4F46E5 !important;
    background: #EEF2FF !important;
    transform: translateY(-2px);
    box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.1);
}
footer {
    display: none !important;
}
"""

with gr.Blocks(title="NovaBot | MercaNova") as demo:
    gr.HTML(
        """
        <section id="header">
            <h1 style="margin: 0; font-size: 2rem; font-weight: 700; display: flex; align-items: center; gap: 10px;">
                🛍️ NovaBot
                <span style="font-size: 1.1rem; font-weight: 400; opacity: 0.85;">por MercaNova</span>
            </h1>
            <p style="margin: 5px 0 0 0; font-size: 1.05rem; opacity: 0.9;">
                Tu asistente de compras inteligente
            </p>
            <div class="badge-container">
                <span class="badge">🟢 En línea</span>
                <span class="badge">📦 Catálogo sincronizado</span>
                <span class="badge">✨ Fuentes verificadas</span>
            </div>
        </section>
        """
    )

    with gr.Column(elem_id="chat-panel"):
        # Aseguramos type="messages" para compatibilidad con diccionarios en Gradio 6+
        chatbot = gr.Chatbot(
            value=historial_inicial(),
            height=450,
            show_label=False,
            type="messages" 
        )

        with gr.Row():
            mensaje = gr.Textbox(
                placeholder="Escribí tu consulta sobre MercaNova...",
                show_label=False,
                container=False,
                scale=8
            )
            enviar = gr.Button("Enviar ➤", variant="primary", scale=2)
            limpiar = gr.Button("Limpiar", variant="secondary", scale=1)

        gr.Markdown("<h3 style='color: #374151; margin-top: 15px; margin-bottom: 5px;'>⚡ Consultas rápidas</h3>")

        botones = []
        with gr.Row():
            for titulo, pregunta in consultas[:3]:
                boton = gr.Button(titulo, elem_classes=["quick-button"])
                botones.append((boton, pregunta))

        with gr.Row():
            for titulo, pregunta in consultas[3:]:
                boton = gr.Button(titulo, elem_classes=["quick-button"])
                botones.append((boton, pregunta))

        gr.Markdown(
            "<p style='text-align: center; color: #9CA3AF; font-size: 0.85rem; margin-top: 15px;'>"
            "MercaNova es una empresa ficticia creada para el Challenge Alura Agente."
            "</p>"
        )

    # Eventos
    enviar.click(fn=enviar_mensaje, inputs=[mensaje, chatbot], outputs=[mensaje, chatbot])
    mensaje.submit(fn=enviar_mensaje, inputs=[mensaje, chatbot], outputs=[mensaje, chatbot])
    limpiar.click(fn=limpiar_chat, inputs=[], outputs=[chatbot, mensaje])

    for boton, pregunta in botones:
        def ejecutar_rapida(historial, p=pregunta):
            return enviar_mensaje(p, historial)
        
        boton.click(fn=ejecutar_rapida, inputs=[chatbot], outputs=[mensaje, chatbot])

# ==========================================
# 5. EJECUCIÓN (LISTO PARA RENDER)
# ==========================================
if __name__ == "__main__":
    print(f"NovaBot iniciado con {TOTAL_PAGINAS} páginas y {len(FRAGMENTOS)} fragmentos.")
    print(f"Modelo configurado: {GEMINI_MODEL}")
    
    # Lanzamos inyectando el tema, el css y la configuración del puerto
    demo.queue(default_concurrency_limit=4).launch(
        server_name="0.0.0.0",
        server_port=PORT,
        share=False,
        show_error=True,
        theme=tema,
        css=css
    )