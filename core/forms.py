import re

from django import forms
from allauth.account.forms import SignupForm

from core.colombia_geo import ciudad_choices_for_departamento, departamento_choices, nombre_departamento
from core.models import AppModule, Sede, User, UserAppPermission, generate_unique_username
from hechos.models import (
    AdminEscuela,
    CapacidadCoordinador,
    Estudiante,
    Profesor,
    Escuela,
    EscuelaPrograma,
    EscuelaProgramaPlantilla,
    NivelPrograma,
    NivelProgramaPlantilla,
    capacidades_default_por_tipo,
    default_anio_escuela,
)


MSG_DOCUMENTO_YA_EXISTE = (
    "Este usuario ya existe. Ingresa con tu número de documento y contraseña "
    "(si te registró un profesor, no hace falta volver a crear la cuenta)."
)


def documento_ya_registrado(doc: str) -> bool:
    """True si el documento ya identifica a un usuario o estudiante en el sistema."""
    value = (doc or "").strip()
    if not value:
        return False
    if User.objects.filter(documento_identidad__iexact=value).exists():
        return True
    if User.objects.filter(username__iexact=value).exists():
        return True
    if Estudiante.objects.filter(numero_documento__iexact=value).exists():
        return True
    return False


def _normalize_and_validate_documento_plausible(raw: str, tipo: str) -> str:
    """
    Comprueba que el documento tenga formato y longitud razonables (no consulta registros oficiales).
    """
    tipo = (tipo or Estudiante.TipoDocumento.CC).strip() or Estudiante.TipoDocumento.CC
    s = (raw or "").strip()
    if not s:
        raise forms.ValidationError("El número de documento es obligatorio.")

    if tipo in (Estudiante.TipoDocumento.CC, Estudiante.TipoDocumento.TI):
        digits = re.sub(r"[\s.\-]", "", s)
        if not digits.isdigit():
            raise forms.ValidationError(
                "El número de documento solo puede contener dígitos (puede usar puntos o espacios como separadores)."
            )
        if len(digits) < 6 or len(digits) > 10:
            raise forms.ValidationError(
                "El número de documento debe tener entre 6 y 10 dígitos."
            )
        if len(set(digits)) == 1:
            raise forms.ValidationError("Ese número de documento no parece válido.")
        return digits

    if tipo == Estudiante.TipoDocumento.CE:
        cleaned = re.sub(r"[\s.\-]", "", s).upper()
        if not re.fullmatch(r"[A-Z0-9]{3,12}", cleaned):
            raise forms.ValidationError(
                "El número de documento debe tener entre 3 y 12 letras o números, sin caracteres especiales."
            )
        if len(set(cleaned)) == 1:
            raise forms.ValidationError("Ese número de documento no parece válido.")
        return cleaned

    # Pasaporte
    cleaned = re.sub(r"\s+", "", s).upper()
    if not re.fullmatch(r"[A-Z0-9]{5,14}", cleaned):
        raise forms.ValidationError(
            "El número de documento debe tener entre 5 y 14 letras o números."
        )
    if len(set(cleaned)) == 1:
        raise forms.ValidationError("Ese número de documento no parece válido.")
    return cleaned


class StudentSignupForm(SignupForm):
    first_name = forms.CharField(max_length=150, label="Nombres")
    last_name = forms.CharField(max_length=150, label="Apellidos")
    genero = forms.ChoiceField(
        choices=Estudiante.Genero.choices,
        label="Género",
        required=True,
    )
    estado_civil = forms.ChoiceField(
        choices=Estudiante.EstadoCivil.choices,
        label="Estado civil",
        required=True,
    )
    tipo_documento = forms.ChoiceField(
        choices=Estudiante.TipoDocumento.choices,
        label="Tipo de documento",
    )
    phone = forms.CharField(
        max_length=15,
        label="Celular (WhatsApp)",
        help_text="Solo números (10 a 15 dígitos).",
    )
    fecha_nacimiento = forms.DateField(required=True, label="Fecha de nacimiento")

    direccion_detallada = forms.CharField(required=False, label="Direccion de residencia", max_length=500)
    barrio = forms.CharField(required=False, label="Barrio", max_length=120)
    departamento = forms.ChoiceField(
        choices=[("", "Seleccione departamento")],
        label="Departamento",
        required=True,
    )
    ciudad = forms.ChoiceField(
        choices=[("", "Primero seleccione departamento")],
        label="Ciudad o municipio",
        required=True,
    )
    autoriza_tratamiento_datos = forms.BooleanField(
        required=True,
        label="Autorizo a HechosHub el tratamiento de mis datos personales.",
        error_messages={"required": "Debes autorizar el tratamiento de datos para continuar."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dept_choices = [("", "Seleccione departamento")] + departamento_choices()
        self.fields["departamento"].choices = dept_choices

        dep_id = None
        if self.data:
            dep_id = self.data.get("departamento")
        if dep_id:
            city_choices = [("", "Seleccione ciudad o municipio")] + ciudad_choices_for_departamento(dep_id)
        else:
            city_choices = [("", "Primero seleccione departamento")]
        self.fields["ciudad"].choices = city_choices
        self.fields["autoriza_tratamiento_datos"].widget.attrs.update(
            {"class": "h-4 w-4 rounded border-stone-400 text-stone-800 focus:ring-stone-300"}
        )
        if "username" in self.fields:
            self.fields["username"].label = "Numero de documento"
        if "phone" in self.fields:
            self.fields["phone"].widget.attrs.update(
                {
                    "inputmode": "numeric",
                    "maxlength": "15",
                    "autocomplete": "tel",
                    "pattern": "[0-9]{10,15}",
                }
            )
        # Contraseña = número de documento; no se pide en el formulario.
        for _pw in ("password1", "password2"):
            self.fields.pop(_pw, None)

    def clean_phone(self):
        raw = (self.cleaned_data.get("phone") or "").strip()
        digits = re.sub(r"\D", "", raw)
        if not digits:
            raise forms.ValidationError("El celular es obligatorio.")
        if len(digits) < 10:
            raise forms.ValidationError("Ingresa un celular válido (al menos 10 dígitos).")
        if len(digits) > 15:
            raise forms.ValidationError("El número parece demasiado largo.")
        return digits

    def clean_username(self):
        tipo = (self.data.get("tipo_documento") or "").strip() or Estudiante.TipoDocumento.CC
        normalized = _normalize_and_validate_documento_plausible(
            self.cleaned_data.get("username", ""), tipo
        )
        self.cleaned_data["username"] = normalized
        if documento_ya_registrado(normalized):
            raise forms.ValidationError(MSG_DOCUMENTO_YA_EXISTE)
        return super().clean_username()

    def clean(self):
        cleaned = super().clean()
        # Sin campos de contraseña en UI: fijar password = documento antes de guardar.
        doc = (cleaned.get("username") or "").strip()
        if doc:
            cleaned["password1"] = doc
            cleaned["password2"] = doc
        dep = cleaned.get("departamento")
        ciu = (cleaned.get("ciudad") or "").strip()
        if dep and ciu:
            permitidas = {c for c, _ in ciudad_choices_for_departamento(dep)}
            if ciu not in permitidas:
                self.add_error("ciudad", "Elija un municipio valido para el departamento seleccionado.")
        return cleaned

    def save(self, request):
        # Misma regla que matrícula por profesor: contraseña inicial = documento.
        doc = (self.cleaned_data.get("username") or "").strip()
        self.cleaned_data["password1"] = doc
        self.cleaned_data["password2"] = doc
        user = super().save(request)
        user.first_name = (self.cleaned_data.get("first_name") or "").strip()
        user.last_name = (self.cleaned_data.get("last_name") or "").strip()
        user.phone = (self.cleaned_data.get("phone") or "").strip()
        user.role = "user"
        email = (self.cleaned_data.get("email") or "").strip()
        user.email = email.lower() if email else None
        user.tipo_documento = self.cleaned_data.get("tipo_documento") or User.TipoDocumento.CC
        user.documento_identidad = doc
        direccion_det = (self.cleaned_data.get("direccion_detallada") or "").strip()
        barrio = (self.cleaned_data.get("barrio") or "").strip()
        departamento = (self.cleaned_data.get("departamento") or "").strip()
        ciudad = (self.cleaned_data.get("ciudad") or "").strip()
        user.direccion = direccion_det
        user.barrio = barrio
        user.departamento = departamento
        user.ciudad = ciudad
        # Por si el adapter no aplicó password1 (edge cases).
        user.set_password(doc)
        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "phone",
                "role",
                "email",
                "tipo_documento",
                "documento_identidad",
                "direccion",
                "barrio",
                "departamento",
                "ciudad",
                "password",
            ]
        )

        Estudiante.objects.update_or_create(
            user=user,
            defaults={
                "genero": self.cleaned_data.get("genero"),
                "estado_civil": self.cleaned_data.get("estado_civil"),
                "tipo_documento": self.cleaned_data.get("tipo_documento"),
                "numero_documento": (self.cleaned_data.get("username") or "").strip(),
                "fecha_nacimiento": self.cleaned_data.get("fecha_nacimiento"),
                "direccion": direccion_det,
            },
        )

        hechos_module = AppModule.objects.filter(name="hechos").first()
        if hechos_module:
            UserAppPermission.objects.get_or_create(
                user=user,
                app_module=hechos_module,
                defaults={
                    "can_view": True,
                    "can_edit": False,
                    "can_delete": False,
                    "can_manage": False,
                },
            )

        return user


class SedeForm(forms.ModelForm):
    nombre = forms.CharField(required=True, label="Nombre")
    imagen_referencia = forms.ImageField(required=False, label="Imagen referencia")
    direccion = forms.CharField(required=False, label="Dirección")
    departamento = forms.ChoiceField(
        choices=[("", "Seleccione departamento")],
        label="Departamento",
        required=False,
    )
    ciudad = forms.ChoiceField(
        choices=[("", "Primero seleccione departamento")],
        label="Ciudad o municipio",
        required=False,
    )
    telefono = forms.CharField(required=False, label="Teléfono")
    email = forms.EmailField(required=False, label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        file_input_class = (
            "w-full rounded-xl border-2 border-dashed border-stone-300 bg-stone-50 px-4 py-3 "
            "text-sm text-slate-700 shadow-sm transition hover:border-stone-400 "
            "focus:outline-none focus:ring-4 focus:ring-stone-200"
        )

        dept_choices = [("", "Seleccione departamento")] + departamento_choices()
        self.fields["departamento"].choices = dept_choices

        dep_id = None
        if self.data:
            dep_id = self.data.get("departamento")
        elif self.instance and self.instance.pk and self.instance.departamento:
            dep_id = self.instance.departamento

        if dep_id:
            self.fields["ciudad"].choices = [
                ("", "Seleccione ciudad o municipio"),
            ] + ciudad_choices_for_departamento(dep_id)
        else:
            self.fields["ciudad"].choices = [("", "Primero seleccione departamento")]

        self.fields["nombre"].widget.attrs.update({"class": input_class, "placeholder": "Ej. Hechos Norte"})
        self.fields["departamento"].widget.attrs.update({"class": input_class})
        self.fields["ciudad"].widget.attrs.update({"class": input_class})
        self.fields["telefono"].widget.attrs.update({"class": input_class, "placeholder": "Opcional"})
        self.fields["email"].widget.attrs.update({"class": input_class, "placeholder": "Opcional"})

        self.fields["direccion"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 3,
                "placeholder": "Opcional",
            }
        )
        self.fields["imagen_referencia"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})

    def clean(self):
        cleaned = super().clean()
        dep = (cleaned.get("departamento") or "").strip()
        ciu = (cleaned.get("ciudad") or "").strip()

        if dep and not ciu:
            self.add_error("ciudad", "Seleccione municipio o vacíe el departamento.")
        if ciu and not dep:
            self.add_error("departamento", "Seleccione departamento o vacíe la ciudad.")
        if dep and ciu and not self.has_error("departamento") and not self.has_error("ciudad"):
            permitidas = {c for c, _ in ciudad_choices_for_departamento(dep)}
            if ciu not in permitidas:
                self.add_error("ciudad", "Elija un municipio válido para el departamento seleccionado.")

        nombre = (cleaned.get("nombre") or "").strip()
        if nombre and not self.has_error("departamento") and not self.has_error("ciudad"):
            qs = Sede.objects.filter(
                nombre__iexact=nombre,
                departamento=dep,
                ciudad=ciu,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    None,
                    "Ya existe una sede con este nombre en la misma ubicación.",
                )
        return cleaned

    class Meta:
        model = Sede
        fields = [
            "nombre",
            "imagen_referencia",
            "direccion",
            "departamento",
            "ciudad",
            "telefono",
            "email",
        ]


class EscuelaSedeBasicaForm(forms.ModelForm):
    """Crear o editar escuela desde coordinación de sede: solo nombre y descripción."""

    class Meta:
        model = Escuela
        fields = ("nombre", "descripcion")
        labels = {
            "nombre": "Nombre de la escuela",
            "descripcion": "Descripción",
        }

    def __init__(self, sede, *args, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["nombre"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Escuela de nuevos creyentes"}
        )
        self.fields["descripcion"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 3,
                "placeholder": "Propósito, público u objetivos de la escuela",
            }
        )

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Indica un nombre para la escuela.")
        return nombre

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        nombre = (cleaned.get("nombre") or "").strip()
        if not nombre:
            return cleaned
        if self.instance.pk:
            anio = self.instance.anio
            ciclo = self.instance.ciclo
        else:
            anio = default_anio_escuela()
            ciclo = Escuela.Ciclo.A
        qs = Escuela.objects.filter(
            sede=self.sede,
            nombre__iexact=nombre,
            anio=anio,
            ciclo=ciclo,
            is_active=True,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            if self.instance.pk:
                msg = "Ya existe otra escuela con el mismo nombre, año y ciclo en esta sede."
            else:
                msg = (
                    "Ya existe una escuela con el mismo nombre para el año en curso y ciclo A. "
                    "Usa otro nombre o revisa si la escuela anterior sigue activa."
                )
            self.add_error(None, msg)
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.sede = self.sede
        if commit:
            obj.save()
        return obj


class NivelProgramaForm(forms.Form):
    """Alta de un nivel del programa para la sede (número de nivel, nombre, descripción opcional)."""

    jerarquia = forms.IntegerField(
        min_value=0,
        label="Nivel",
        help_text="Número entero (0 = Fundamentos, 1, 2, 3…). Define el orden; puede ser mayor si creas niveles propios (ej. 11).",
    )
    nombre = forms.CharField(
        max_length=200,
        label="Nombre",
        help_text='Se concatena con el número: «Nivel N: …». Ej. «Sanos y Libres». En el nivel 0 puedes usar «Fundamentos» o dejarlo vacío.',
        required=False,
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción del nivel",
        help_text="Opcional. Se muestra debajo del título del nivel en «Escuelas del programa» (enfoque, propósito).",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Ej. Enfocado en la restauración integral de la persona…",
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
    )

    def __init__(self, *args, sede=None, **kwargs):
        self.sede = sede
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["jerarquia"].widget.attrs.update(
            {"class": input_class, "inputmode": "numeric", "min": "0"}
        )
        self.fields["nombre"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Sanos y Libres, Iglesia superior…"}
        )

    def clean(self):
        cleaned = super().clean()
        if self._errors or self.sede is None:
            return cleaned
        j = cleaned.get("jerarquia")
        if j is None:
            return cleaned
        nombre = (cleaned.get("nombre") or "").strip()
        if j == 0:
            cleaned["nombre"] = nombre or "Fundamentos"
        elif not nombre:
            raise forms.ValidationError(
                {"nombre": "Indica el nombre (excepto en el nivel 0)."}
            )
        if NivelPrograma.objects.filter(sede=self.sede, jerarquia=j, is_active=True).exists():
            raise forms.ValidationError(
                {"jerarquia": "Ya existe un nivel con este número en la sede."}
            )
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        return cleaned


class NivelProgramaEditForm(forms.Form):
    """Edición de un nivel existente (misma validación que el alta, excluyendo el propio registro)."""

    jerarquia = forms.IntegerField(
        min_value=0,
        label="Nivel",
        help_text="Número entero (0 = Fundamentos, 1, 2, 3…). Debe ser único en la sede.",
    )
    nombre = forms.CharField(
        max_length=200,
        label="Nombre",
        help_text='Se muestra como «Nivel N: …». Ej. «Sanos y Libres». En el nivel 0: «Fundamentos» o vacío.',
        required=False,
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción del nivel",
        help_text="Opcional. Se muestra debajo del título del nivel en «Escuelas del programa».",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Ej. Enfocado en la restauración integral de la persona…",
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
    )

    def __init__(self, *args, sede=None, nivel_pk=None, **kwargs):
        self.sede = sede
        self.nivel_pk = nivel_pk
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["jerarquia"].widget.attrs.update(
            {"class": input_class, "inputmode": "numeric", "min": "0"}
        )
        self.fields["nombre"].widget.attrs.update(
            {"class": input_class, "placeholder": "Ej. Sanos y Libres, Iglesia superior…"}
        )

    def clean(self):
        cleaned = super().clean()
        if self._errors or self.sede is None or self.nivel_pk is None:
            return cleaned
        j = cleaned.get("jerarquia")
        if j is None:
            return cleaned
        nombre = (cleaned.get("nombre") or "").strip()
        if j == 0:
            cleaned["nombre"] = nombre or "Fundamentos"
        elif not nombre:
            raise forms.ValidationError(
                {"nombre": "Indica el nombre (excepto en el nivel 0)."}
            )
        qs = NivelPrograma.objects.filter(sede=self.sede, jerarquia=j, is_active=True).exclude(
            pk=self.nivel_pk
        )
        if qs.exists():
            raise forms.ValidationError(
                {"jerarquia": "Ya existe otro nivel con este número en la sede."}
            )
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        return cleaned


class EscuelaProgramaForm(forms.Form):
    """Definición de escuela en el programa (nivel, nombre, descripción). No es la instancia por ciclo."""

    nombre = forms.CharField(
        max_length=200,
        label="Nombre de la escuela",
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(
            attrs={
                "rows": 7,
                "placeholder": "Describe el propósito o enfoque de esta escuela en el programa",
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
        help_text="Texto libre opcional (propósito, público o enfoque).",
    )
    tiene_matricula = forms.BooleanField(
        required=False,
        label="Tiene matrícula",
        help_text="Si aplica cobro de matrícula, indica el valor en pesos colombianos (enteros).",
    )
    costo_matricula_cop = forms.IntegerField(
        required=False,
        min_value=1,
        label="Costo de matrícula (COP)",
        help_text="Solo números enteros, sin decimales.",
    )

    def __init__(self, *args, sede=None, checkbox_js_class="js-programa-tiene-matricula", **kwargs):
        self._checkbox_js_class = checkbox_js_class
        self.sede = sede
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        if sede is None:
            raise ValueError("EscuelaProgramaForm requiere sede=")
        np = forms.ModelChoiceField(
            queryset=NivelPrograma.objects.filter(sede=sede, is_active=True).order_by(
                "jerarquia", "nombre"
            ),
            label="Nivel",
            empty_label=None,
        )
        np.label_from_instance = lambda obj: obj.titulo_acordeon()
        self.fields["nivel_programa"] = np
        self.fields["nivel_programa"].widget.attrs.update({"class": input_class})
        self.fields["nombre"].widget.attrs.update(
            {
                "class": input_class,
                "placeholder": (
                    "Ej. Sanidad Integral o Transformación para Mujeres…"
                ),
            }
        )
        self.fields["costo_matricula_cop"].widget.attrs.update(
            {
                "class": input_class,
                "placeholder": "Ej. 50000",
                "inputmode": "numeric",
                "min": "1",
                "step": "1",
            }
        )
        self.fields["tiene_matricula"].widget.attrs.update(
            {
                "class": (
                    "h-4 w-4 rounded border-stone-300 text-amber-600 "
                    "focus:ring-amber-500 " + self._checkbox_js_class
                ),
            }
        )

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Indica el nombre de la escuela.")
        return nombre

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        tiene = bool(cleaned.get("tiene_matricula"))
        costo = cleaned.get("costo_matricula_cop")
        if tiene:
            if costo is None:
                self.add_error(
                    "costo_matricula_cop",
                    "Indica el costo de matrícula en pesos colombianos (enteros).",
                )
        else:
            cleaned["costo_matricula_cop"] = None
        return cleaned


class NivelProgramaPlantillaForm(forms.Form):
    """Alta de nivel global (todas las sedes heredan)."""

    jerarquia = forms.IntegerField(
        min_value=1,
        label="Jerarquía",
        help_text="Número de orden que verán las sedes (1 = Fundamentos, 2, 3…). Debe ser único en todo el programa.",
    )
    nombre = forms.CharField(
        max_length=200,
        label="Nombre",
        help_text='Se concatena con el número: «Nivel N: …».',
        required=False,
    )
    descripcion = forms.CharField(
        required=False,
        label="Descripción del nivel",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["jerarquia"].widget.attrs.update(
            {"class": input_class, "inputmode": "numeric", "min": "1"}
        )
        self.fields["nombre"].widget.attrs.update({"class": input_class})

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        j_visible = cleaned.get("jerarquia")
        if j_visible is None:
            return cleaned
        j = j_visible - 1  # jerarquia interna: 0 = Fundamentos
        nombre = (cleaned.get("nombre") or "").strip()
        if j == 0:
            cleaned["nombre"] = nombre or "Fundamentos"
        elif not nombre:
            raise forms.ValidationError(
                {"nombre": "Indica el nombre (excepto en el nivel 1)."}
            )
        if NivelProgramaPlantilla.objects.filter(jerarquia=j).exists():
            raise forms.ValidationError(
                {"jerarquia": "Ya existe un nivel con este número en el programa global."}
            )
        cleaned["jerarquia"] = j
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        return cleaned


class NivelProgramaPlantillaEditForm(forms.Form):
    """Edición de nivel global."""

    jerarquia = forms.IntegerField(
        min_value=1,
        label="Nivel",
        help_text="Número que verán las sedes (1 = Fundamentos, 2, 3…).",
    )
    nombre = forms.CharField(max_length=200, label="Nombre", required=False)
    descripcion = forms.CharField(
        required=False,
        label="Descripción del nivel",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
    )

    def __init__(self, *args, nivel_plantilla_pk=None, **kwargs):
        self.nivel_plantilla_pk = nivel_plantilla_pk
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        self.fields["jerarquia"].widget.attrs.update(
            {"class": input_class, "inputmode": "numeric", "min": "1"}
        )
        self.fields["nombre"].widget.attrs.update({"class": input_class})

    def clean(self):
        cleaned = super().clean()
        if self._errors or self.nivel_plantilla_pk is None:
            return cleaned
        j_visible = cleaned.get("jerarquia")
        if j_visible is None:
            return cleaned
        j = j_visible - 1  # jerarquia interna: 0 = Fundamentos
        nombre = (cleaned.get("nombre") or "").strip()
        if j == 0:
            cleaned["nombre"] = nombre or "Fundamentos"
        elif not nombre:
            raise forms.ValidationError(
                {"nombre": "Indica el nombre (excepto en el nivel 1)."}
            )
        qs = NivelProgramaPlantilla.objects.filter(jerarquia=j).exclude(pk=self.nivel_plantilla_pk)
        if qs.exists():
            raise forms.ValidationError(
                {"jerarquia": "Ya existe otro nivel con este número en el programa global."}
            )
        cleaned["jerarquia"] = j
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        return cleaned


class EscuelaProgramaPlantillaForm(forms.Form):
    """Escuela del programa a nivel global."""

    nombre = forms.CharField(max_length=200, label="Nombre de la escuela")
    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(
            attrs={
                "rows": 7,
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
        help_text="Texto libre opcional (propósito, público o enfoque).",
    )
    tiene_matricula = forms.BooleanField(
        required=False,
        label="Tiene matrícula",
        help_text="Si aplica cobro de matrícula, indica el valor en pesos colombianos (enteros).",
    )
    costo_matricula_cop = forms.IntegerField(
        required=False,
        min_value=1,
        label="Costo de matrícula (COP)",
        help_text="Solo números enteros, sin decimales.",
    )

    def __init__(
        self,
        *args,
        checkbox_js_class="js-programa-tiene-matricula",
        nivel_plantilla_queryset=None,
        **kwargs,
    ):
        self._checkbox_js_class = checkbox_js_class
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        nq = nivel_plantilla_queryset
        if nq is None:
            nq = NivelProgramaPlantilla.objects.order_by("jerarquia", "nombre")
        np = forms.ModelChoiceField(
            queryset=nq,
            label="Nivel",
            empty_label=None,
        )
        np.label_from_instance = lambda obj: obj.titulo_acordeon()
        self.fields["nivel_plantilla"] = np
        self.fields["nivel_plantilla"].widget.attrs.update({"class": input_class})
        self.fields["nombre"].widget.attrs.update({"class": input_class})
        self.fields["costo_matricula_cop"].widget.attrs.update(
            {
                "class": input_class,
                "placeholder": "Ej. 50000",
                "inputmode": "numeric",
                "min": "1",
                "step": "1",
            }
        )
        self.fields["tiene_matricula"].widget.attrs.update(
            {
                "class": (
                    "h-4 w-4 rounded border-stone-300 text-amber-600 "
                    "focus:ring-amber-500 " + self._checkbox_js_class
                ),
            }
        )

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Indica el nombre de la escuela.")
        return nombre

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        tiene = bool(cleaned.get("tiene_matricula"))
        costo = cleaned.get("costo_matricula_cop")
        if tiene:
            if costo is None:
                self.add_error(
                    "costo_matricula_cop",
                    "Indica el costo de matrícula en pesos colombianos (enteros).",
                )
        else:
            cleaned["costo_matricula_cop"] = None
        nl = cleaned.get("nivel_plantilla")
        nombre = cleaned.get("nombre")
        if nl and nombre and EscuelaProgramaPlantilla.objects.filter(
            nivel_plantilla=nl, nombre__iexact=nombre.strip()
        ).exists():
            self.add_error("nombre", "Ya existe una escuela con este nombre en ese nivel.")
        return cleaned


class EscuelaProgramaPlantillaEditForm(forms.Form):
    """Edición de escuela global del programa."""

    nombre = forms.CharField(max_length=200, label="Nombre de la escuela")
    descripcion = forms.CharField(
        required=False,
        label="Descripción",
        widget=forms.Textarea(
            attrs={
                "rows": 7,
                "class": (
                    "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
                    "text-slate-900 shadow-sm transition focus:border-stone-500 "
                    "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
                ),
            }
        ),
    )
    tiene_matricula = forms.BooleanField(required=False, label="Tiene matrícula")
    costo_matricula_cop = forms.IntegerField(
        required=False,
        min_value=1,
        label="Costo de matrícula (COP)",
    )

    def __init__(
        self,
        *args,
        escuela_plantilla_pk=None,
        prefix="programa_edit",
        checkbox_js_class="js-programa-edit-tiene-matricula",
        nivel_plantilla_queryset=None,
        **kwargs,
    ):
        self.escuela_plantilla_pk = escuela_plantilla_pk
        self._checkbox_js_class = checkbox_js_class
        super().__init__(*args, prefix=prefix, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        nq = nivel_plantilla_queryset
        if nq is None:
            nq = NivelProgramaPlantilla.objects.order_by("jerarquia", "nombre")
        np = forms.ModelChoiceField(
            queryset=nq,
            label="Nivel",
            empty_label=None,
        )
        np.label_from_instance = lambda obj: obj.titulo_acordeon()
        self.fields["nivel_plantilla"] = np
        self.fields["nivel_plantilla"].widget.attrs.update({"class": input_class})
        self.fields["nombre"].widget.attrs.update({"class": input_class})
        self.fields["costo_matricula_cop"].widget.attrs.update(
            {
                "class": input_class,
                "placeholder": "Ej. 50000",
                "inputmode": "numeric",
                "min": "1",
                "step": "1",
            }
        )
        self.fields["tiene_matricula"].widget.attrs.update(
            {
                "class": (
                    "h-4 w-4 rounded border-stone-300 text-amber-600 "
                    "focus:ring-amber-500 " + self._checkbox_js_class
                ),
            }
        )

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise forms.ValidationError("Indica el nombre de la escuela.")
        return nombre

    def clean(self):
        cleaned = super().clean()
        if self._errors:
            return cleaned
        cleaned["descripcion"] = (cleaned.get("descripcion") or "").strip()
        tiene = bool(cleaned.get("tiene_matricula"))
        costo = cleaned.get("costo_matricula_cop")
        if tiene:
            if costo is None:
                self.add_error(
                    "costo_matricula_cop",
                    "Indica el costo de matrícula en pesos colombianos (enteros).",
                )
        else:
            cleaned["costo_matricula_cop"] = None
        nl = cleaned.get("nivel_plantilla")
        nombre = (cleaned.get("nombre") or "").strip()
        if nl and nombre and self.escuela_plantilla_pk is not None:
            dup = EscuelaProgramaPlantilla.objects.filter(
                nivel_plantilla=nl, nombre__iexact=nombre
            ).exclude(pk=self.escuela_plantilla_pk)
            if dup.exists():
                self.add_error("nombre", "Ya existe otra escuela con este nombre en ese nivel.")
        return cleaned


class CoordinadorForm(forms.Form):
    nombres = forms.CharField(max_length=150, label="Nombre(s)")
    apellidos = forms.CharField(max_length=150, label="Apellido(s)")
    tipo_documento = forms.ChoiceField(
        choices=User.TipoDocumento.choices,
        label="Tipo de documento",
        initial=User.TipoDocumento.CC,
    )
    documento_identidad = forms.CharField(
        max_length=32,
        label="Número de identificación",
        help_text="Según el tipo elegido (cédula: solo números).",
    )
    celular = forms.CharField(
        max_length=15,
        required=False,
        label="Celular (WhatsApp)",
        help_text="Opcional. Solo números (10 a 15 dígitos). Para contacto y WhatsApp.",
    )
    email = forms.EmailField(required=False, label="Correo electrónico")
    avatar = forms.ImageField(required=False, label="Foto")
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Contraseña", required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirmar contraseña", required=False)

    def __init__(self, *args, admin_profile=None, allowed_tipos=None, **kwargs):
        self.admin_profile = admin_profile
        self.allowed_tipos = tuple(allowed_tipos) if allowed_tipos else (AdminEscuela.TipoCoordinador.SEDE,)
        super().__init__(*args, **kwargs)
        input_class = (
            "w-full rounded-xl border-2 border-stone-300 bg-stone-50 px-4 py-3 "
            "text-slate-900 shadow-sm transition focus:border-stone-500 "
            "focus:bg-white focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        file_input_class = (
            "w-full rounded-xl border-2 border-dashed border-stone-300 bg-stone-50 px-4 py-3 "
            "text-sm text-slate-700 shadow-sm transition hover:border-stone-400 "
            "focus:outline-none focus:ring-4 focus:ring-stone-200"
        )
        for _key in ("nombres", "apellidos", "documento_identidad"):
            self.fields[_key].widget.attrs.update({"class": input_class, "autocomplete": "off"})
        self.fields["celular"].widget.attrs.update(
            {
                "class": input_class,
                "autocomplete": "tel",
                "inputmode": "numeric",
                "maxlength": "15",
                "pattern": r"[0-9]*",
                "title": "Solo números, sin espacios ni símbolos.",
            }
        )
        self.fields["tipo_documento"].widget.attrs.update(
            {"class": input_class, "autocomplete": "off"}
        )
        self.fields["email"].widget.attrs.update({"class": input_class, "autocomplete": "email"})
        self.fields["avatar"].widget = forms.FileInput(
            attrs={"class": file_input_class, "accept": "image/*", "autocomplete": "off"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": input_class, "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": input_class, "autocomplete": "new-password"}
        )
        labels = dict(AdminEscuela.TipoCoordinador.choices)
        choices = [(v, labels[v]) for v in self.allowed_tipos]
        self.tipo_coordinador_automatico = len(choices) > 1
        if self.tipo_coordinador_automatico:
            # El tipo y el cargo se deducen de las tareas marcadas (varias → "combinado").
            pass
        elif len(choices) == 1:
            self.fields["tipo_coordinador"] = forms.ChoiceField(
                choices=choices,
                initial=choices[0][0],
                widget=forms.HiddenInput(),
            )
        else:
            self.fields["tipo_coordinador"] = forms.ChoiceField(
                choices=choices,
                label="Tipo de coordinador",
                widget=forms.Select(attrs={"class": input_class, "autocomplete": "off"}),
            )

        catalog = list(
            CapacidadCoordinador.objects.order_by("orden", "nombre").values_list("codigo", "nombre")
        )
        self.fields["capacidades"] = forms.MultipleChoiceField(
            required=False,
            choices=catalog,
            label="Tareas en Hechos",
            widget=forms.CheckboxSelectMultiple(
                attrs={"class": "capacidad-check rounded border-stone-300 text-stone-800 focus:ring-stone-300"}
            ),
        )
        self.fields["capacidades_orden"] = forms.CharField(required=False, widget=forms.HiddenInput())

        initial_caps = self._initial_capacidades_list()
        self.fields["capacidades"].initial = initial_caps
        self.fields["capacidades_orden"].initial = ",".join(initial_caps)

    def _initial_capacidades_list(self):
        if self.admin_profile:
            asigs = self.admin_profile.capacidad_asignaciones.select_related("capacidad").order_by(
                "orden", "id"
            )
            codes = [a.capacidad.codigo for a in asigs]
            if codes:
                return codes
            if self.admin_profile.capacidades_explicitas:
                return []
            return capacidades_default_por_tipo(self.admin_profile.tipo_coordinador)
        tipo = (getattr(self, "initial", None) or {}).get("tipo_coordinador")
        if not tipo and self.allowed_tipos:
            tipo = self.allowed_tipos[0]
        if not tipo:
            tipo = AdminEscuela.TipoCoordinador.ACADEMICO
        return capacidades_default_por_tipo(tipo)

    def clean_documento_identidad(self):
        raw = (self.cleaned_data.get("documento_identidad") or "").strip()
        if not raw:
            raise forms.ValidationError("El número de identificación es obligatorio.")
        tipo = (self.cleaned_data.get("tipo_documento") or User.TipoDocumento.CC).strip()
        normalized = _normalize_and_validate_documento_plausible(raw, tipo)
        User = AdminEscuela._meta.get_field("user").remote_field.model
        qs = User.objects.filter(documento_identidad__iexact=normalized)
        if self.admin_profile:
            qs = qs.exclude(pk=self.admin_profile.user_id)
        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con este número de identificación.")
        return normalized

    def clean_celular(self):
        raw = (self.cleaned_data.get("celular") or "").strip()
        if not raw:
            return ""
        if not raw.isdigit():
            raise forms.ValidationError(
                "El celular solo puede contener números (sin espacios, + ni guiones)."
            )
        if len(raw) < 10:
            raise forms.ValidationError("Ingresa un celular válido (al menos 10 dígitos).")
        if len(raw) > 15:
            raise forms.ValidationError("El número parece demasiado largo.")
        return raw

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return None
        User = AdminEscuela._meta.get_field("user").remote_field.model
        qs = User.objects.filter(email__iexact=email)
        if self.admin_profile:
            qs = qs.exclude(pk=self.admin_profile.user_id)
        if qs.exists():
            raise forms.ValidationError("Ese correo ya está registrado.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if self.admin_profile:
            if password1 or password2:
                if password1 != password2:
                    raise forms.ValidationError("Las contraseñas no coinciden.")
        else:
            if not password1 or not password2:
                raise forms.ValidationError("Debes definir una contraseña para el coordinador.")
            if password1 != password2:
                raise forms.ValidationError("Las contraseñas no coinciden.")

        valid = {c[0] for c in self.fields["capacidades"].choices}
        caps = [c for c in (cleaned_data.get("capacidades") or []) if c in valid]

        if getattr(self, "tipo_coordinador_automatico", False):
            post_tipo = (self.data.get("tipo_coordinador") or "").strip()
            if (
                not caps
                and post_tipo == AdminEscuela.TipoCoordinador.SEDE
                and post_tipo in self.allowed_tipos
            ):
                cleaned_data["tipo_coordinador"] = AdminEscuela.TipoCoordinador.SEDE
            elif not caps and not self.admin_profile:
                if post_tipo in self.allowed_tipos:
                    caps = capacidades_default_por_tipo(post_tipo)
                else:
                    bootstrap = next(
                        (t for t in self.allowed_tipos if t != AdminEscuela.TipoCoordinador.SEDE),
                        AdminEscuela.TipoCoordinador.ACADEMICO,
                    )
                    caps = capacidades_default_por_tipo(bootstrap)
            if cleaned_data.get("tipo_coordinador") == AdminEscuela.TipoCoordinador.SEDE:
                pass
            elif not caps:
                raise forms.ValidationError("Selecciona al menos una tarea en Hechos.")
            elif "tipo_coordinador" not in cleaned_data or not cleaned_data.get("tipo_coordinador"):
                cleaned_data["tipo_coordinador"] = AdminEscuela.tipo_coordinador_desde_capacidades(caps)
        else:
            tipo = cleaned_data.get("tipo_coordinador")
            if tipo and self.allowed_tipos and tipo not in self.allowed_tipos:
                raise forms.ValidationError("El tipo de coordinador seleccionado no está permitido.")
            if not caps and not self.admin_profile:
                caps = capacidades_default_por_tipo(tipo)

        tipo = cleaned_data.get("tipo_coordinador")
        if (
            tipo
            and self.allowed_tipos
            and tipo not in self.allowed_tipos
            and tipo != AdminEscuela.TipoCoordinador.COMBINADO
        ):
            raise forms.ValidationError(
                "El tipo de coordinador no está permitido en este contexto."
            )

        caps_set = set(caps)
        orden_raw = (cleaned_data.get("capacidades_orden") or "").strip()
        orden_in = [x.strip() for x in orden_raw.split(",") if x.strip()]
        orden_final = []
        for c in orden_in:
            if c in caps_set and c not in orden_final:
                orden_final.append(c)
        catalog_order = [c[0] for c in self.fields["capacidades"].choices]
        for c in catalog_order:
            if c in caps_set and c not in orden_final:
                orden_final.append(c)
        cleaned_data["capacidades"] = caps
        cleaned_data["_capacidades_orden_final"] = orden_final

        return cleaned_data

    def save(self, user_model, sede, hechos_module):
        data = self.cleaned_data
        tipo = data["tipo_coordinador"]
        orden_final = data.get("_capacidades_orden_final") or []
        if tipo == AdminEscuela.TipoCoordinador.SEDE:
            cargo = AdminEscuela.cargo_para_tipo(tipo, sede.nombre)
        else:
            cargo = AdminEscuela.cargo_para_capacidades(orden_final, sede.nombre)
        first_name = (data.get("nombres") or "").strip()
        last_name = (data.get("apellidos") or "").strip()
        email = data.get("email")

        if self.admin_profile:
            user = self.admin_profile.user
            prev_email = user.email
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            if prev_email != email:
                seed = email or data.get("documento_identidad") or ""
                user.username = generate_unique_username(user_model, seed, exclude_pk=user.pk)
            user.role = "app_admin"
            user.sede = sede
            user.is_staff = True
            if data.get("avatar"):
                user.avatar = data["avatar"]
            if data.get("password1"):
                user.set_password(data["password1"])
            user.tipo_documento = data["tipo_documento"]
            user.documento_identidad = data["documento_identidad"]
            user.phone = (data.get("celular") or "").strip() or None
            user.save()

            self.admin_profile.sede = sede
            self.admin_profile.tipo_coordinador = tipo
            self.admin_profile.cargo = cargo
            self.admin_profile.save()
            admin_profile = self.admin_profile
        else:
            seed = email or data.get("documento_identidad") or ""
            username = generate_unique_username(user_model, seed, exclude_pk=None)
            user = user_model.objects.create_user(
                username=username,
                email=email,
                password=data["password1"],
                first_name=first_name,
                last_name=last_name,
                role="app_admin",
                sede=sede,
                is_active=True,
                is_staff=True,
                avatar=data.get("avatar"),
                tipo_documento=data["tipo_documento"],
                documento_identidad=data["documento_identidad"],
                phone=(data.get("celular") or "").strip() or None,
            )
            admin_profile = AdminEscuela.objects.create(
                user=user,
                sede=sede,
                tipo_coordinador=tipo,
                cargo=cargo,
                is_active=True,
            )

        orden_caps = data.get("_capacidades_orden_final") or []
        admin_profile.sync_capacidades(orden_caps)

        if hechos_module:
            UserAppPermission.objects.update_or_create(
                user=user,
                app_module=hechos_module,
                defaults={
                    "can_view": True,
                    "can_edit": True,
                    "can_delete": True,
                    "can_manage": True,
                },
            )

        return admin_profile


class CoordinadorRolesForm(forms.Form):
    """
    El coordinador de sede se autoasigna tareas en Hechos (académico, pedagógico,
    financiero, logístico), sin tocar datos personales ni el tipo «sede».
    """

    def __init__(self, *args, admin_profile=None, **kwargs):
        self.admin_profile = admin_profile
        super().__init__(*args, **kwargs)

        catalog = list(
            CapacidadCoordinador.objects.order_by("orden", "nombre").values_list("codigo", "nombre")
        )
        self.fields["capacidades"] = forms.MultipleChoiceField(
            required=False,
            choices=catalog,
            label="Tareas en Hechos",
            widget=forms.CheckboxSelectMultiple(
                attrs={"class": "capacidad-check rounded border-stone-300 text-stone-800 focus:ring-stone-300"}
            ),
        )
        self.fields["capacidades_orden"] = forms.CharField(required=False, widget=forms.HiddenInput())

        initial_caps = []
        if self.admin_profile:
            asigs = self.admin_profile.capacidad_asignaciones.select_related("capacidad").order_by(
                "orden", "id"
            )
            initial_caps = [a.capacidad.codigo for a in asigs]
        self.fields["capacidades"].initial = initial_caps
        self.fields["capacidades_orden"].initial = ",".join(initial_caps)

    def clean(self):
        cleaned_data = super().clean()
        valid = {c[0] for c in self.fields["capacidades"].choices}
        caps = [c for c in (cleaned_data.get("capacidades") or []) if c in valid]
        caps_set = set(caps)

        orden_raw = (cleaned_data.get("capacidades_orden") or "").strip()
        orden_in = [x.strip() for x in orden_raw.split(",") if x.strip()]
        orden_final = [c for c in orden_in if c in caps_set]
        catalog_order = [c[0] for c in self.fields["capacidades"].choices]
        for c in catalog_order:
            if c in caps_set and c not in orden_final:
                orden_final.append(c)

        cleaned_data["capacidades"] = caps
        cleaned_data["_capacidades_orden_final"] = orden_final
        return cleaned_data


class DirectorProfesorEditForm(forms.Form):
    """
    Edición de profesor desde la consola del director (todas las sedes).
    """

    first_name = forms.CharField(max_length=150, label="Nombre")
    last_name = forms.CharField(max_length=150, label="Apellido")
    email = forms.EmailField(label="Correo electrónico")
    phone = forms.CharField(max_length=20, required=False, label="Celular (WhatsApp)")
    tipo_documento = forms.ChoiceField(
        choices=[("", "Sin especificar")] + list(User.TipoDocumento.choices),
        required=False,
        label="Tipo de documento",
    )
    documento_identidad = forms.CharField(
        max_length=32,
        required=False,
        label="Número de documento",
    )
    sede = forms.ModelChoiceField(
        queryset=Sede.objects.none(),
        required=False,
        label="Sede",
        empty_label="Sin sede asignada",
    )
    is_active = forms.BooleanField(required=False, label="Perfil activo")
    password1 = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="Nueva contraseña",
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        label="Confirmar contraseña",
    )

    def __init__(self, *args, user_instance, **kwargs):
        self.user_instance = user_instance
        super().__init__(*args, **kwargs)
        self.fields["sede"].queryset = Sede.objects.filter(is_active=True).order_by("nombre")
        ctrl = (
            "mt-1 block w-full rounded-lg border border-stone-300 px-3 py-2 "
            "text-sm text-stone-900 shadow-sm focus:border-amber-500 focus:ring-amber-500"
        )
        for fname in (
            "first_name",
            "last_name",
            "email",
            "phone",
            "documento_identidad",
            "password1",
            "password2",
        ):
            self.fields[fname].widget.attrs.setdefault("class", ctrl)
        self.fields["tipo_documento"].widget.attrs.setdefault("class", ctrl)
        self.fields["sede"].widget.attrs.setdefault("class", ctrl)
        self.fields["is_active"].widget.attrs.setdefault(
            "class", "h-4 w-4 rounded border-stone-300 text-amber-600 focus:ring-amber-500"
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError("El correo es obligatorio.")
        if (
            User.objects.filter(email__iexact=email)
            .exclude(pk=self.user_instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Ya existe otro usuario con ese correo.")
        return email

    def clean_documento_identidad(self):
        raw = (self.cleaned_data.get("documento_identidad") or "").strip()
        if not raw:
            return ""
        tipo = (self.cleaned_data.get("tipo_documento") or "").strip() or User.TipoDocumento.CC
        normalized = _normalize_and_validate_documento_plausible(raw, tipo)
        dup = (
            User.objects.filter(documento_identidad=normalized)
            .exclude(pk=self.user_instance.pk)
            .exists()
        )
        if dup:
            raise forms.ValidationError("Ese documento ya está registrado en otro usuario.")
        return normalized

    def clean(self):
        data = super().clean()
        p1 = (data.get("password1") or "").strip()
        p2 = (data.get("password2") or "").strip()
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError("Las contraseñas no coinciden.")
            if len(p1) < 8:
                raise forms.ValidationError("La contraseña debe tener al menos 8 caracteres.")
        return data

    def apply_to(self, profesor: Profesor) -> None:
        data = self.cleaned_data
        u = profesor.user
        u.first_name = (data["first_name"] or "").strip()
        u.last_name = (data["last_name"] or "").strip()
        u.email = data["email"]
        u.phone = (data.get("phone") or "").strip() or None
        tipo = (data.get("tipo_documento") or "").strip() or User.TipoDocumento.CC
        u.tipo_documento = tipo
        doc = data.get("documento_identidad") or ""
        u.documento_identidad = doc or None
        pwd = (data.get("password1") or "").strip()
        if pwd:
            u.set_password(pwd)
        u.save()

        profesor.sede = data.get("sede")
        profesor.is_active = bool(data.get("is_active"))
        profesor.save()
