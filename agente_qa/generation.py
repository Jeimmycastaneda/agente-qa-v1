"""Orquestación de generación QA.

Capa de transición de la migración: mantiene la interfaz de generación en
agente_qa/generation.py, respetando la estructura objetivo de mao-dev, sin
copiar lógica funcional desde mao-dev. La implementación Gemini existente
permanece encapsulada en providers/gemini.py hasta completar la separación
provider/orquestador.
"""

from agente_qa.providers.gemini import (
    generate_qa_data as _generate_qa_data,
    load_prompt,
    validate_qa_structure,
)


def generate_qa_data(
    prompt_text,
    source_content,
    api_key,
    model_name,
    temperature=0.1,
    max_retries=2,
    initial_wait=10,
):
    """Genera los datos QA usando el proveedor Gemini actual."""
    return _generate_qa_data(
        prompt_text=prompt_text,
        source_content=source_content,
        api_key=api_key,
        model_name=model_name,
        temperature=temperature,
        max_retries=max_retries,
        initial_wait=initial_wait,
    )
