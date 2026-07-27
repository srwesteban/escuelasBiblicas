"""
Documento de identidad del estudiante: User.documento_identidad es canónico;
Estudiante.numero_documento se mantiene sincronizado para consultas y legado.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hechos.models import Estudiante


def documento_numero_estudiante(estudiante: Estudiante) -> str:
    n = (estudiante.numero_documento or "").strip()
    if n:
        return n
    user = getattr(estudiante, "user", None)
    if user is None:
        return ""
    return (user.documento_identidad or "").strip()


def guardar_documento_estudiante(
    estudiante: Estudiante,
    doc: str,
    tipo_documento: str | None = None,
) -> str:
    """Escribe el mismo número en User y Estudiante. Devuelve el doc normalizado."""
    from hechos.models import Estudiante

    doc = (doc or "").strip()
    if not doc:
        return ""
    tipo = (tipo_documento or estudiante.tipo_documento or Estudiante.TipoDocumento.CC).strip()

    estudiante.numero_documento = doc
    estudiante.tipo_documento = tipo
    estudiante.save(update_fields=["numero_documento", "tipo_documento", "updated_at"])

    user = estudiante.user
    user.documento_identidad = doc
    if tipo:
        user.tipo_documento = tipo
    user.save(update_fields=["documento_identidad", "tipo_documento", "updated_at"])
    return doc


def sincronizar_documento_estudiante(estudiante: Estudiante) -> str:
    """
    Rellena el campo vacío desde la otra fuente. Si ambos existen y difieren,
    prioriza User.documento_identidad.
    """
    user_doc = (estudiante.user.documento_identidad or "").strip()
    est_doc = (estudiante.numero_documento or "").strip()
    if user_doc and est_doc and user_doc != est_doc:
        return guardar_documento_estudiante(estudiante, user_doc, estudiante.tipo_documento)
    if user_doc and not est_doc:
        estudiante.numero_documento = user_doc
        estudiante.save(update_fields=["numero_documento", "updated_at"])
        return user_doc
    if est_doc and not user_doc:
        estudiante.user.documento_identidad = est_doc
        estudiante.user.save(update_fields=["documento_identidad", "updated_at"])
        return est_doc
    return user_doc or est_doc
