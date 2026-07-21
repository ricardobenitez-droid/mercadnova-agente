# 🛍️ NovaBot — Asistente Virtual para MercaNova

**NovaBot** es un agente conversacional e-commerce impulsado por Inteligencia Artificial y arquitectura **RAG (Retrieval-Augmented Generation)**. Fue desarrollado para responder consultas de usuarios sobre envíos, pagos, devoluciones, garantías y políticas de **MercaNova** utilizando únicamente la documentación oficial cargada en el sistema.

> 🚀 **Proyecto desarrollado para el Challenge Alura Agente.**

---

## ✨ Características Principales

- 🔍 **Búsqueda Inteligente (RAG + BM25):** Recupera fragmentos de información relevantes directamente del documento oficial PDF de la tienda.
- 🔤 **Normalización y Sinónimos:** Reconoce plurales, elimina tildes e interpreta sinónimos clave en español (ej. *precio* ➔ *tarifa/costo*, *envíos* ➔ *entregas/despachos*).
- 📌 **Citación de Fuentes:** Cada respuesta indica explícitamente las páginas consultadas del PDF para brindar máxima transparencia y evitar alucinaciones.
- 🎨 **Interfaz Moderna e Intuitiva:** Desarrollada con **Gradio Blocks**, con temas personalizados, estilo corporativo y botones de consultas rápidas.
- 🧠 **Memoria Contextual:** Mantiene el seguimiento de la conversación reciente.

---

## 🛠️ Tecnologías Utilizadas

- **Lenguaje:** Python 3.12+
- **Modelo LLM:** Google Gemini API (`google-genai`)
- **Interfaz Web:** Gradio
- **Procesamiento PDF:** PyPDF
- **Motor de Búsqueda:** BM25 (`rank-bm25`)
- **Despliegue:** Render / GitHub

---

## 📁 Estructura del Proyecto

```text
mercadnova-agente/
├── data/
│   └── Documentacion_MercaNova_Ecommerce.pdf   # Documentación base
├── .env.example                                # Plantilla de variables de entorno
├── .gitignore                                  # Archivos ignorados por Git
├── app.py                                      # Código principal de la aplicación
├── README.md                                   # Documentación del repositorio
└── requirements.txt                            # Dependencias del proyecto