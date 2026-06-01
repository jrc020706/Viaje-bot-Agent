# Reporte de Aseguramiento de Calidad (QA) — ViajeBot ✈️

Este documento detalla el estado actual del proyecto **ViajeBot** en términos de calidad de software y las recomendaciones para alcanzar un nivel de producción robusto.

## 1. Estado Actual: **Nivel Inicial / Prototipo Avanzado**
El proyecto es funcional y cuenta con una arquitectura modular sólida, pero depende altamente de la verificación manual.

### Fortalezas actualizadas:
- **Resiliencia en Herramientas:** Implementación de `@_retry` y manejo de excepciones en `tools.py`.
- **Traducción Integral:** Código, comentarios y lógica de negocio estandarizados en inglés.
- **Arquitectura Documentada:** Flujo de datos claro entre FastAPI, LangGraph y los modelos de Groq/Gemini.

## 2. Áreas de Mejora Prioritarias

### A. Pruebas Automatizadas (Testing)
Para llegar a un nivel de QA profesional, es imperativo implementar:
- **Unit Tests (`pytest`):** Validar de forma aislada herramientas como el conversor de moneda y el buscador de imágenes.
- **Integration Tests:** Evaluar la cadena de LangGraph con un dataset de preguntas "Golden" para asegurar que el modelo no alucine o ignore herramientas.
- **UI Tests (Playwright):** Automatizar la verificación del frontend para evitar regresiones visuales o errores de sintaxis en el HTML.

### B. Estándares de Código y Linting
- **Resolución de Dependencias:** Configurar el entorno virtual (`.venv`) en el CI para eliminar las advertencias de "Import not found".
- **Refactorización de Tipos:** Ajustar los `Type Hints` en `agent_core.py` y `utils.py` para cumplir estrictamente con los estándares de Python modernos.

### C. Observabilidad
- **Logging Estructurado:** Sustituir los `print()` por un sistema de logs (`logging`) que permita filtrar por niveles (DEBUG, INFO, ERROR).
- **Trazabilidad:** Implementar herramientas como LangSmith para auditar el razonamiento del agente en cada paso.

## 3. Hoja de Ruta Sugerida (Roadmap)
1. **Fase 1:** Implementar suite de `pytest` básica para `backend/tools.py`.
2. **Fase 2:** Configurar GitHub Actions para ejecutar tests en cada commit.
3. **Fase 3:** Migrar la extracción de datos en `run_agent` a modelos de validación con **Pydantic**.
