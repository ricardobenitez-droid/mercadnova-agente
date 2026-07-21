from __future__ import annotations
import os
import re
from pathlib import Path
import gradio as gr
from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader
from rank_bm25 import BM25Okapi

# Carga .env únicamente durante pruebas locales.
# En Render, las variables se configuran desde el dashboard.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

PDF_PATH = Path(
    os.getenv(
        "PDF_PATH",
        str(BASE_DIR / "data" / "NovaStore.pdf")
    )
)

# Render entrega automáticamente PORT.
PORT = int(os.getenv("PORT", "10000"))

# ==========================================
# VALIDACIONES INICIALES
# ==========================================
if not GEMINI_API_KEY:
    raise RuntimeError("Falta la variable de entorno GEMINI_API_KEY.")
if not GEMINI_MODEL:
    raise RuntimeError("Falta la variable de entorno GEMINI_MODEL.")
if not PDF_PATH.exists():
    raise FileNotFoundError(f"No se encontró el PDF: {PDF_PATH}")

client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# LÓGICA DE EXTRACCIÓN Y BÚSQUEDA EN PDF
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
            fragmentos.append({
                "page": pagina,
                "text": contenido
            })
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

# Cargar el PDF y crear el buscador (BM25)
FRAGMENTOS, TOTAL_PAGINAS = cargar_documento(PDF_PATH)

def tokenizar(texto: str) -> list[str]:
    return re.findall(r"[a-záéíóúüñ0-9]+", texto.lower())

CORPUS_TOKENIZADO = [tokenizar(fragmento["text"]) for fragmento in FRAGMENTOS]
BM25 = BM25Okapi(CORPUS_TOKENIZADO)

def recuperar_fragmentos(pregunta: str, cantidad: int = 5) -> list[dict]:
    tokens = tokenizar(pregunta)
    puntajes = BM25.get_scores(tokens)
    indices = sorted(range(len(puntajes)), key=lambda indice: puntajes[indice], reverse=True)[:cantidad]
    return [FRAGMENTOS[indice] for indice in indices]

# ==========================================
# LÓGICA DEL AGENTE
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
        if not isinstance(contenido, str):
            continue
        nombre = "Usuario" if rol == "user" else "Asistente"
        lineas.append(f"{nombre}: {contenido}")
    return "\n".join(lineas) if lineas else "Sin conversación anterior."

def responder_ecommerce(pregunta, historial=None):
    pregunta = (pregunta or "").strip()
    if not pregunta:
        return "Escribí una pregunta sobre MercaNova."

    documentos = recuperar_fragmentos(pregunta, cantidad=5)
    bloques_contexto = []
    paginas_usadas = []
    
    for documento in documentos:
        pagina = documento["page"]
        paginas_usadas.append(pagina)
        bloques_contexto.append(f"[Página {pagina}]\n{documento['text']}")
        
    contexto = "\n\n---\n\n".join(bloques_contexto)
    historial_texto = formatear_historial(historial)
    paginas_ordenadas = sorted(set(paginas_usadas))
    
    prompt = f"""Sos NovaBot, el asistente documental de MercaNova,
una tienda e-commerce ficticia creada para el Challenge Alura Agente.

REGLAS OBLIGATORIAS:
Respondé en español claro y directo.
Utilizá exclusivamente el CONTEXTO DOCUMENTAL.
No inventes precios, plazos, políticas, teléfonos, correos, productos ni procedimientos.
Conservá exactamente los montos, límites y plazos.
Si la respuesta no aparece en el contexto, respondé:
  "No encontré esa información en la documentación disponible de MercaNova."
No afirmes que MercaNova es una empresa real.
Finalizá mencionando las páginas consultadas.

HISTORIAL RECIENTE:
{historial_texto}

CONTEXTO DOCUMENTAL:
{contexto}

PREGUNTA:
{pregunta}

Redactá la respuesta:"""

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

# ==========================================
# INTERFAZ GRÁFICA Y EJECUCIÓN
# ==========================================
tema = gr.themes.Soft()
css = ""

# Aquí se construye la variable "demo"
with gr.Blocks() as demo:
    gr.Markdown("# 🤖 NovaBot - MercaNova")
    # type="messages" asegura la compatibilidad con el nuevo formato de Gradio para el historial
    gr.ChatInterface(fn=responder_ecommerce)

if __name__ == "__main__":
    print(f"NovaBot iniciado con {TOTAL_PAGINAS} páginas y {len(FRAGMENTOS)} fragmentos.")
    print(f"Modelo configurado: {GEMINI_MODEL}")
    
    demo.queue(default_concurrency_limit=4).launch(
        server_name="0.0.0.0",
        server_port=PORT,
        share=False,
        show_error=True,
        theme=tema,
        css=css
    )