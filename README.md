# MARCO MVP

Workbench local de coautoría científica con arquitectura hexagonal:
dominio (`core/domain`), casos de uso (`core/application`), puertos
(`core/ports`) y adaptadores (`core/adapters`).

## Uso local

```powershell
pip install -e ".[test]"
pytest
streamlit run ui/app.py  # opcional: pip install -e ".[ui]"
```

El comando anterior funciona directamente desde el checkout. Si Streamlit
reporta `ModuleNotFoundError: No module named 'core'`, confirma que estás en
la raíz del repositorio (`cd marco-mvp`) o instala el proyecto en modo editable:

```powershell
python -m pip install -e ".[ui]"
```

El proveedor predeterminado es `MockLLMAdapter`; no descarga modelos ni hace
llamadas de red. `HybridRAGStore` combina BM25 local con embeddings
deterministas por hashing. OpenAI, Ollama, PyMuPDF y Streamlit son opcionales.
La trayectoria forense se guarda como `trajectory.jsonl` (JSONL append-only,
separada del contexto que pueda podarse) y encadena hashes para detectar
alteraciones. `governance.yaml` es opcional y permite parametrizar plantilla,
presupuesto y semáforos semánticos (por defecto verde `0.75`, rojo `0.50`).

El flujo exige firma humana en `TRANSITION_GATE` y `EXPORT`. Los borradores
respetan un presupuesto de tokens aproximado y toda evidencia recuperada queda
disponible como citas en `DraftResult`.

## Experimento MARCO

El workbench usa las cuatro fases `PARAMETRIZATION`, `CURATION`, `DRAFTING` y
`ASSEMBLY`. Cada avance exige una firma HITL válida. Cargue uno o más PDFs en
la barra lateral, pulse **Indexar**, busque evidencia, genere una sección con
`MockLLM`, revise el texto y ejecute los niveles de gobernanza antes de firmar.
La auditoría JSONL puede exportarse como reporte de transparencia Secc. 4.6
(JSON o Markdown), incluyendo eventos, fases, tokens, latencia, citas y cadena.

PyMuPDF es opcional (`pip install -e ".[pdf]"`). Para PDFs escaneados, OCR es
explícito y opt-in (`pip install -e ".[ocr]"`, además de Tesseract instalado);
si se solicita sin dependencias se devuelve un error claro. `GrobidParser` está disponible
como adaptador opt-in para instalaciones locales de Grobid; requiere que el
servicio esté activo y nunca se invoca implícitamente. Sin PyMuPDF se pueden
usar textos planos.
No hay llamadas de red implícitas: el proveedor predeterminado es MockLLM y
las representaciones vectoriales son deterministas. El corpus real de 18
papers se proporciona externamente y no se incluye en este MVP.
