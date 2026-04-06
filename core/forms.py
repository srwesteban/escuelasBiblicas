from django import forms
from django.forms import inlineformset_factory
from allauth.account.forms import SignupForm

from core.colombia_geo import ciudad_choices_for_departamento, departamento_choices, nombre_departamento
from core.models import AppModule, PastorSede, Sede, User, UserAppPermission, generate_unique_username
from hechos.models import AdminEscuela, Estudiante, Escuela, default_anio_escuela


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
    numero_documento = forms.CharField(max_length=30, label="Numero de documento")
    phone = forms.CharField(max_length=20, label="Celular")
    fecha_nacimiento = forms.DateField(required=True, label="Fecha de nacimiento")

    direccion_detallada = forms.CharField(required=True, label="Direccion de residencia", max_length=500)
    barrio = forms.CharField(required=True, label="Barrio", max_length=120)
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

    def clean(self):
        cleaned = super().clean()
        dep = cleaned.get("departamento")
        ciu = (cleaned.get("ciudad") or "").strip()
        if dep and ciu:
            permitidas = {c for c, _ in ciudad_choices_for_departamento(dep)}
            if ciu not in permitidas:
                self.add_error("ciudad", "Elija un municipio valido para el departamento seleccionado.")
        return cleaned

    def clean_numero_documento(self):
        numero = (self.cleaned_data.get("numero_documento") or "").strip()
        if not numero:
            raise forms.ValidationError("El numero de documento es obligatorio.")
        exists = Estudiante.objects.filter(numero_documento__iexact=numero).exists()
        if exists:
            raise forms.ValidationError("Ya existe un estudiante con este numero de documento.")
        return numero

    def save(self, request):
        user = super().save(request)
        user.first_name = (self.cleaned_data.get("first_name") or "").strip()
        user.last_name = (self.cleaned_data.get("last_name") or "").strip()
        user.phone = (self.cleaned_data.get("phone") or "").strip()
        user.role = "user"
        user.save(update_fields=["first_name", "last_name", "phone", "role", "username"])

        Estudiante.objects.update_or_create(
            user=user,
            defaults={
                "genero": self.cleaned_data.get("genero"),
                "estado_civil": self.cleaned_data.get("estado_civil"),
                "tipo_documento": self.cleaned_data.get("tipo_documento"),
                "numero_documento": self.cleaned_data.get("numero_documento"),
                "fecha_nacimiento": self.cleaned_data.get("fecha_nacimiento"),
                "direccion": ", ".join(
                    [
                        (self.cleaned_data.get("direccion_detallada") or "").strip(),
                        (self.cleaned_data.get("barrio") or "").strip(),
                        ", ".join(
                            p
                            for p in [
                                (self.cleaned_data.get("ciudad") or "").strip(),
                                nombre_departamento(self.cleaned_data.get("departamento")),
                            ]
                            if p
                        ),
                    ]
                ).strip(", "),
                "iglesia": "",
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
    pastor_responsable = forms.CharField(required=False, label="Pastor responsable")
    foto_pastor = forms.ImageField(required=False, label="Foto pastor")

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
        self.fields["pastor_responsable"].widget.attrs.update({"class": input_class, "placeholder": "Opcional"})

        self.fields["direccion"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 3,
                "placeholder": "Opcional",
            }
        )
        self.fields["imagen_referencia"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})
        self.fields["foto_pastor"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})

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
            "pastor_responsable",
            "foto_pastor",
        ]


class PastorSedeForm(forms.ModelForm):
    nombre = forms.CharField(required=False, label="Nombre")
    foto = forms.ImageField(required=False, label="Foto")

    class Meta:
        model = PastorSede
        fields = ["nombre", "foto"]

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
        self.fields["nombre"].widget.attrs.update({"class": input_class, "placeholder": "Nombre del pastor opcional"})
        self.fields["foto"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})


PastorSedeFormSet = inlineformset_factory(
    Sede,
    PastorSede,
    form=PastorSedeForm,
    extra=0,
    can_delete=True,
)


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
            grupo = self.instance.grupo
        else:
            anio = default_anio_escuela()
            ciclo = Escuela.Ciclo.A
            grupo = 1
        qs = Escuela.objects.filter(
            sede=self.sede,
            nombre__iexact=nombre,
            anio=anio,
            ciclo=ciclo,
            grupo=grupo,
            is_active=True,
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            if self.instance.pk:
                msg = "Ya existe otra escuela con el mismo nombre, año, ciclo y grupo en esta sede."
            else:
                msg = (
                    "Ya existe una escuela con el mismo nombre para el año en curso, ciclo A y grupo 1. "
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


class CoordinadorForm(forms.Form):
    nombres = forms.CharField(max_length=150, label="Nombre(s)")
    apellidos = forms.CharField(max_length=150, label="Apellido(s)")
    email = forms.EmailField(label="Correo electrónico")
    avatar = forms.ImageField(required=False, label="Foto")
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Contraseña", required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirmar contraseña", required=False)
    is_active = forms.BooleanField(required=False, initial=True, label="Activo")

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
        for _key in ("nombres", "apellidos"):
            self.fields[_key].widget.attrs.update({"class": input_class, "autocomplete": "off"})
        self.fields["email"].widget.attrs.update({"class": input_class, "autocomplete": "off"})
        self.fields["avatar"].widget = forms.FileInput(
            attrs={"class": file_input_class, "accept": "image/*", "autocomplete": "off"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": input_class, "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": input_class, "autocomplete": "new-password"}
        )
        self.fields["is_active"].widget.attrs.update({"class": "h-4 w-4 rounded border-stone-400 text-stone-800 focus:ring-stone-300"})

        labels = dict(AdminEscuela.TipoCoordinador.choices)
        choices = [(v, labels[v]) for v in self.allowed_tipos]
        if len(choices) == 1:
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

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return email
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

        tipo = cleaned_data.get("tipo_coordinador")
        if tipo and self.allowed_tipos and tipo not in self.allowed_tipos:
            raise forms.ValidationError("El tipo de coordinador seleccionado no está permitido.")

        return cleaned_data

    def save(self, user_model, sede, hechos_module):
        data = self.cleaned_data
        tipo = data["tipo_coordinador"]
        cargo = AdminEscuela.cargo_para_tipo(tipo, sede.nombre)
        first_name = (data.get("nombres") or "").strip()
        last_name = (data.get("apellidos") or "").strip()
        email = data["email"]

        if self.admin_profile:
            user = self.admin_profile.user
            prev_email = user.email
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            if prev_email != email:
                user.username = generate_unique_username(user_model, email, exclude_pk=user.pk)
            user.role = "app_admin"
            user.sede = sede
            user.is_active = data["is_active"]
            user.is_staff = True
            if data.get("avatar"):
                user.avatar = data["avatar"]
            if data.get("password1"):
                user.set_password(data["password1"])
            user.save()

            self.admin_profile.sede = sede
            self.admin_profile.tipo_coordinador = tipo
            self.admin_profile.cargo = cargo
            self.admin_profile.is_active = data["is_active"]
            self.admin_profile.save()
            admin_profile = self.admin_profile
        else:
            username = generate_unique_username(user_model, email, exclude_pk=None)
            user = user_model.objects.create_user(
                username=username,
                email=email,
                password=data["password1"],
                first_name=first_name,
                last_name=last_name,
                role="app_admin",
                sede=sede,
                is_active=data["is_active"],
                is_staff=True,
                avatar=data.get("avatar"),
            )
            admin_profile = AdminEscuela.objects.create(
                user=user,
                sede=sede,
                tipo_coordinador=tipo,
                cargo=cargo,
                is_active=data["is_active"],
            )

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
