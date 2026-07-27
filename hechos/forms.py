import os
from decimal import Decimal
from pathlib import Path

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.validators import FileExtensionValidator
from django.db.models import Sum

from core.utils_money import format_cop_puntos, normalize_cop_money_input
from hechos.models import (
    ActividadEscuela,
    ArchivoRecursoEscuela,
    EntregaActividad,
    ItemInventario,
    Ofrenda,
    PresupuestoEvento,
    QuejaReclamo,
    RecaudoOcasional,
    Salon,
)


def ingresos_totales_sede(sede) -> Decimal:
    """Suma ofrendas + recaudos ocasionales de la sede (ingresos registrados)."""
    of_sum = Ofrenda.objects.filter(sede=sede).aggregate(s=Sum("valor"))["s"] or Decimal("0")
    rec_sum = RecaudoOcasional.objects.filter(sede=sede).aggregate(s=Sum("monto"))["s"] or Decimal("0")
    return of_sum + rec_sum


class COPDecimalField(forms.DecimalField):
    """Acepta montos con formato colombiano (2.000,50) además de 2000 o 2000.5."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, str):
            n = normalize_cop_money_input(value)
            if n == "":
                return None
            value = n
        return super().to_python(value)


class QuejaReclamoForm(forms.ModelForm):
    """Asunto = categoría (queja, reclamo, sugerencia, solicitud); mensaje = cuerpo."""

    asunto = forms.ChoiceField(
        label="Asunto",
        choices=QuejaReclamo.Tipo.choices,
    )

    class Meta:
        model = QuejaReclamo
        fields = ["mensaje"]
        labels = {"mensaje": "Mensaje"}
        widgets = {
            "mensaje": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["asunto"].widget.attrs.update({"class": input_class})
        self.fields["mensaje"].widget.attrs.update({"class": input_class})
        if self.instance.pk:
            self.fields["asunto"].initial = self.instance.tipo


class OfrendaForm(forms.ModelForm):
    class Meta:
        model = Ofrenda
        fields = ["valor"]  # "escuela" se agrega dinámicamente si hace falta
        labels = {
            "valor": "Valor (COP)",
        }

    def __init__(self, *args, escuelas_qs=None, include_escuela=False, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        if include_escuela:
            self.fields["escuela"] = forms.ModelChoiceField(
                label="Escuela",
                queryset=escuelas_qs if escuelas_qs is not None else Ofrenda.objects.none(),
                empty_label="Selecciona la escuela",
                required=True,
            )
            self.fields["escuela"].widget.attrs.update({"class": input_class})
        orig_valor = self.fields.pop("valor")
        self.fields["valor"] = COPDecimalField(
            label=orig_valor.label,
            required=orig_valor.required,
            max_digits=12,
            decimal_places=2,
            widget=forms.TextInput(
                attrs={
                    "class": f"{input_class} input-cop-money",
                    "placeholder": "0",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
        )

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")
        if valor is None:
            return valor
        if valor <= 0:
            raise forms.ValidationError("El valor debe ser mayor a 0.")
        return valor


class PresupuestoEventoForm(forms.ModelForm):
    """Alta de evento / partida con monto que la sede destina o planea destinar."""

    class Meta:
        model = PresupuestoEvento
        fields = ("nombre", "fecha_evento", "monto_destinado", "notas")
        labels = {
            "nombre": "Nombre del evento o partida",
            "fecha_evento": "Fecha del evento (opcional)",
            "monto_destinado": "Monto a destinar (COP)",
            "notas": "Notas (opcional)",
        }

    def __init__(self, *args, sede=None, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["nombre"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Retiro de jóvenes, compra de biblias…"}
        )
        self.fields["fecha_evento"].widget = forms.DateInput(
            attrs={"type": "date", "class": input_class}
        )
        self.fields["fecha_evento"].required = False
        orig_m = self.fields.pop("monto_destinado")
        self.fields["monto_destinado"] = COPDecimalField(
            label=orig_m.label,
            required=orig_m.required,
            max_digits=14,
            decimal_places=2,
            widget=forms.TextInput(
                attrs={
                    "class": f"{input_class} input-cop-money",
                    "placeholder": "0",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
        )
        self.fields["notas"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 3,
                "placeholder": "Detalle opcional para el equipo financiero",
            }
        )

    def clean_monto_destinado(self):
        v = self.cleaned_data.get("monto_destinado")
        if v is not None and v <= 0:
            raise forms.ValidationError("El monto a destinar debe ser mayor a 0.")
        return v

    def clean(self):
        cleaned = super().clean()
        if self._errors or self.sede is None:
            return cleaned
        monto = cleaned.get("monto_destinado")
        if monto is None:
            return cleaned
        total_in = ingresos_totales_sede(self.sede)
        qs = PresupuestoEvento.objects.filter(sede=self.sede)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        ya = qs.aggregate(s=Sum("monto_destinado"))["s"] or Decimal("0")
        if ya + monto > total_in:
            disponible = total_in - ya
            self.add_error(
                "monto_destinado",
                forms.ValidationError(
                    "No puedes destinar más que los ingresos de la sede (ofrendas y recaudos ocasionales). "
                    f"Máximo en este registro: {format_cop_puntos(disponible)}.",
                ),
            )
        return cleaned


class RecaudoOcasionalForm(forms.ModelForm):
    """Ingreso puntual (extra, sobrante de evento, etc.) registrado por coordinación financiera."""

    class Meta:
        model = RecaudoOcasional
        fields = ("fecha", "monto", "concepto", "detalle")
        labels = {
            "fecha": "Fecha",
            "monto": "Monto recaudado (COP)",
            "concepto": "Concepto",
            "detalle": "Detalle (opcional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["fecha"].widget = forms.DateInput(attrs={"type": "date", "class": input_class})
        orig_m = self.fields.pop("monto")
        self.fields["monto"] = COPDecimalField(
            label=orig_m.label,
            required=orig_m.required,
            max_digits=14,
            decimal_places=2,
            widget=forms.TextInput(
                attrs={
                    "class": f"{input_class} input-cop-money",
                    "placeholder": "0",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                }
            ),
        )
        self.fields["concepto"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Sobrante del retiro, donación de visitante…"}
        )
        self.fields["detalle"].widget = forms.Textarea(
            attrs={"class": input_class, "rows": 3, "placeholder": "Contexto adicional si lo necesitas"}
        )

    def clean_monto(self):
        v = self.cleaned_data.get("monto")
        if v is not None and v <= 0:
            raise forms.ValidationError("El monto debe ser mayor a 0.")
        return v


class SalonForm(forms.ModelForm):
    class Meta:
        model = Salon
        fields = ("nombre", "codigo", "capacidad_plazas")
        labels = {
            "nombre": "Nombre del salón",
            "codigo": "Código (opcional)",
            "capacidad_plazas": "Capacidad (plazas)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        for name in self.fields:
            self.fields[name].widget.attrs.update({"class": input_class})

    def clean_capacidad_plazas(self):
        n = self.cleaned_data.get("capacidad_plazas")
        if n is not None and n < 1:
            raise forms.ValidationError("La capacidad debe ser al menos 1.")
        return n


class ItemInventarioForm(forms.ModelForm):
    class Meta:
        model = ItemInventario
        fields = ("nombre", "cantidad", "notas")
        labels = {
            "nombre": "Producto",
            "cantidad": "Cantidad",
            "notas": "Notas (opcional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        for name in self.fields:
            self.fields[name].widget.attrs.update({"class": input_class})

    def clean_cantidad(self):
        n = self.cleaned_data.get("cantidad")
        if n is not None and n < 0:
            raise forms.ValidationError("La cantidad no puede ser negativa.")
        return n


class ActividadEscuelaForm(forms.ModelForm):
    """Alta de actividad tipo LMS (Canvas/Moodle: tipo, título, instrucciones, límite, adjunto)."""

    class Meta:
        model = ActividadEscuela
        fields = (
            "tipo",
            "titulo",
            "instrucciones",
            "fecha_limite",
            "puntos_posibles",
            "material_adjunto",
        )
        labels = {
            "tipo": "Tipo de actividad",
            "titulo": "Título",
            "instrucciones": "Instrucciones para el estudiante",
            "fecha_limite": "Fecha y hora límite (opcional)",
            "puntos_posibles": "Puntos posibles (opcional)",
            "material_adjunto": "Material de apoyo (opcional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["tipo"].widget.attrs.update({"class": input_class})
        self.fields["titulo"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Lectura del capítulo 3 · Foro semanal"}
        )
        self.fields["instrucciones"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 6,
                "placeholder": "Qué debe hacer el estudiante, criterios, enlaces útiles…",
            }
        )
        self.fields["fecha_limite"].widget = forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local", "class": input_class},
        )
        self.fields["fecha_limite"].required = False
        self.fields["fecha_limite"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"]
        self.fields["puntos_posibles"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. 10", "inputmode": "decimal"}
        )
        self.fields["material_adjunto"].widget.attrs.update(
            {
                "class": (
                    "block w-full text-sm text-stone-600 "
                    "file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 "
                    "file:bg-violet-100 file:text-violet-900 hover:file:bg-violet-200"
                ),
            }
        )

    def clean_puntos_posibles(self):
        v = self.cleaned_data.get("puntos_posibles")
        if v is not None and v < 0:
            raise forms.ValidationError("Los puntos no pueden ser negativos.")
        return v


class ArchivoRecursoEscuelaForm(forms.ModelForm):
    """Subida de material para la escuela (PDF, Office, imágenes, ZIP)."""

    class Meta:
        model = ArchivoRecursoEscuela
        fields = ("titulo", "descripcion", "archivo")
        labels = {
            "titulo": "Título del recurso",
            "descripcion": "Descripción (opcional)",
            "archivo": "Archivo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["titulo"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Guía de lectura · Tabla de versículos"}
        )
        self.fields["descripcion"].widget = forms.Textarea(
            attrs={"class": input_class, "rows": 3, "placeholder": "Opcional…"}
        )
        self.fields["archivo"].widget.attrs.update(
            {
                "class": (
                    "block w-full text-sm text-stone-600 "
                    "file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 "
                    "file:bg-sky-100 file:text-sky-900 hover:file:bg-sky-200"
                ),
            }
        )

    def clean_archivo(self):
        f = self.cleaned_data.get("archivo")
        if f is None:
            return f
        max_bytes = 20 * 1024 * 1024
        if getattr(f, "size", 0) > max_bytes:
            raise forms.ValidationError("El archivo no puede superar 20 MB.")
        if getattr(f, "size", 0) == 0:
            raise forms.ValidationError("El archivo está vacío (0 bytes).")
        return f


# Mismo criterio que FileField del modelo EntregaActividad (validación en la vista con request.FILES).
ENTREGA_EVIDENCIA_EXTENSIONES = (
    "pdf",
    "doc",
    "docx",
    "odt",
    "txt",
    "rtf",
    "png",
    "jpg",
    "jpeg",
    "webp",
)
entrega_evidencia_archivo_validator = FileExtensionValidator(
    allowed_extensions=ENTREGA_EVIDENCIA_EXTENSIONES,
)


def normalizar_archivo_entrega(uf):
    """
    Texto plano a veces llega sin extensión (.name vacío, 'blob', etc.) o como
    application/octet-stream (Windows). Las imágenes suelen traer .png/.jpg y no necesitan esto.
    Solo actuamos si no hay extensión, para no tocar ficheros rechazables con extensión rara.
    """
    if uf is None or getattr(uf, "size", 0) <= 0:
        return uf
    base = os.path.basename((getattr(uf, "name", None) or "").strip())
    ext = Path(base).suffix[1:].lower() if Path(base).suffix else ""
    if ext in ENTREGA_EVIDENCIA_EXTENSIONES:
        return uf
    if ext != "":
        return uf
    ct = (getattr(uf, "content_type", "") or "").lower()
    if ct in ("text/plain", "text/txt"):
        body = uf.read()
        if hasattr(uf, "seek"):
            uf.seek(0)
        stem = Path(base).stem if base and base.lower() not in ("blob", "file") else ""
        if not stem:
            stem = "evidencia"
        return SimpleUploadedFile(
            f"{stem}.txt",
            body,
            content_type="text/plain",
        )
    if ct == "application/octet-stream" and uf.size <= 512 * 1024:
        body = uf.read()
        if hasattr(uf, "seek"):
            uf.seek(0)
        if b"\x00" in body[: min(8192, len(body))]:
            if hasattr(uf, "seek"):
                uf.seek(0)
            return uf
        decoded_ok = False
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                body[: min(8192, len(body))].decode(enc)
                decoded_ok = True
                break
            except UnicodeDecodeError:
                continue
        if not decoded_ok:
            if hasattr(uf, "seek"):
                uf.seek(0)
            return uf
        stem = Path(base).stem if base and base.lower() not in ("blob", "file") else ""
        if not stem:
            stem = "evidencia"
        return SimpleUploadedFile(f"{stem}.txt", body, content_type="text/plain")
    return uf


class EntregaActividadTextoForm(forms.ModelForm):
    """Solo el texto; el archivo se maneja en la vista con request.FILES (como la foto de perfil)."""

    class Meta:
        model = EntregaActividad
        fields = ("texto",)
        labels = {"texto": "Tu respuesta o trabajo (texto)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["texto"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 10,
                "placeholder": "Escribe aquí tu respuesta, reflexión o desarrollo del ejercicio…",
            }
        )


class EntregaActividadEstudianteForm(forms.ModelForm):
    """Reservado (p. ej. admin); la pantalla de entrega usa EntregaActividadTextoForm + FILES en la vista."""

    class Meta:
        model = EntregaActividad
        fields = ("texto", "archivo")
        labels = {
            "texto": "Tu respuesta o trabajo (texto)",
            "archivo": "Archivo de evidencia (opcional)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["texto"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 10,
                "placeholder": "Escribe aquí tu respuesta, reflexión o desarrollo del ejercicio…",
            }
        )
        self.fields["archivo"].widget = forms.FileInput(
            attrs={
                "class": "sr-only",
                "accept": ".pdf,.doc,.docx,.odt,.txt,.rtf,.png,.jpg,.jpeg,.webp",
                "tabindex": "-1",
            }
        )
        self.fields["archivo"].allow_empty_file = True

    def clean_archivo(self):
        f = self.cleaned_data.get("archivo")
        if f is False:
            return False
        if f is not None and hasattr(f, "size"):
            if f.size > 0:
                return f
            prev = self.instance.archivo if self.instance.pk else None
            if prev and getattr(prev, "name", ""):
                return prev
            return None
        prev = self.instance.archivo if self.instance.pk else None
        if prev and getattr(prev, "name", ""):
            return prev
        return None

    def clean(self):
        cleaned = super().clean()
        texto = (cleaned.get("texto") or "").strip()
        archivo_nuevo = cleaned.get("archivo")
        archivo_previo = self.instance.archivo if self.instance.pk else None
        if not texto and not archivo_nuevo and not archivo_previo:
            raise forms.ValidationError(
                "Debes escribir una respuesta o subir un archivo con contenido "
                "(los archivos vacíos, 0 bytes, no cuentan)."
            )
        return cleaned


class ProfesorEvaluaEntregaForm(forms.ModelForm):
    class Meta:
        model = EntregaActividad
        fields = ("puntaje_asignado", "comentario_docente")
        labels = {
            "puntaje_asignado": "Puntaje",
            "comentario_docente": "Comentario para el estudiante",
        }

    def __init__(self, *args, actividad=None, **kwargs):
        self._actividad = actividad
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm "
            "text-slate-900 shadow-sm focus:border-amber-600/60 focus:outline-none focus:ring-2 focus:ring-amber-500/20"
        )
        self.fields["puntaje_asignado"].widget.attrs.update({"class": input_class, "placeholder": "Ej. 8.5"})
        self.fields["puntaje_asignado"].required = False
        self.fields["comentario_docente"].widget = forms.Textarea(
            attrs={"class": input_class, "rows": 3, "placeholder": "Retroalimentación…"}
        )

    def clean_puntaje_asignado(self):
        v = self.cleaned_data.get("puntaje_asignado")
        if v is None:
            return v
        if v < 0:
            raise forms.ValidationError("El puntaje no puede ser negativo.")
        if self._actividad and self._actividad.puntos_posibles is not None:
            if v > self._actividad.puntos_posibles:
                raise forms.ValidationError(
                    f"No puede superar los puntos posibles de la actividad ({self._actividad.puntos_posibles})."
                )
        return v

