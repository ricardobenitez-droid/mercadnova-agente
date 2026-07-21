# 1. IMPORTACIONES
import gradio as gr
import os
# ... (otras importaciones)

# 2. VARIABLES Y FUNCIONES (Tema, CSS, historial, etc.)
tema = gr.themes.Soft(
    primary_hue="indigo",     
    secondary_hue="violet",   
    neutral_hue="slate",      
    font=[gr.themes.GoogleFont("Inter"), "ui-sans-serif", "system-ui", "sans-serif"]
)
css = """..."""

def enviar_mensaje(mensaje, historial):
    # Aquí va toda la lógica original de tu bot que tenías antes
    historial.append((mensaje, "Respuesta de prueba"))
    return "", historial
    # ...

# 3. CONSTRUCCIÓN DE LA INTERFAZ (Aquí "nace" la variable demo)
with gr.Blocks(title="NovaBot | MercaNova") as demo:
    # ... (todo el código visual, HTML, chat, botones)
    gr.Markdown("Hola, soy la interfaz")
# 4. LANZAMIENTO (Tu código exacto, estrictamente al final)
if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860, # Asegúrate de que PORT esté definido o usa el número directo
        share=False,
        show_error=True,
        theme=tema,
        css=css
    )