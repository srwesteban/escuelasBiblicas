from django import forms
from django.forms import inlineformset_factory
from allauth.account.forms import SignupForm

from core.models import AppModule, PastorSede, Sede, UserAppPermission
from hechos.models import AdminEscuela, Estudiante


class StudentSignupForm(SignupForm):
    def save(self, request):
        user = super().save(request)
        user.role = "user"
        user.save(update_fields=["role", "username"])

        Estudiante.objects.get_or_create(user=user)

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
    direccion = forms.CharField(required=True, label="Dirección")
    ciudad = forms.CharField(required=True, label="Ciudad")
    telefono = forms.CharField(required=False, label="Teléfono")
    email = forms.EmailField(required=False, label="Email")
    pastor_responsable = forms.CharField(required=True, label="Pastor responsable")
    foto_pastor = forms.ImageField(required=False, label="Foto pastor")
    descripcion = forms.CharField(required=False, label="Descripción")

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

        self.fields["nombre"].widget.attrs.update({"class": input_class, "placeholder": "Ej. Hechos Norte"})
        self.fields["ciudad"].widget.attrs.update({"class": input_class, "placeholder": "Ej. Monterrey"})
        self.fields["telefono"].widget.attrs.update({"class": input_class, "placeholder": "Opcional"})
        self.fields["email"].widget.attrs.update({"class": input_class, "placeholder": "Opcional"})
        self.fields["pastor_responsable"].widget.attrs.update({"class": input_class, "placeholder": "Nombre del pastor"})

        self.fields["direccion"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 3,
                "placeholder": "Dirección completa de la sede",
            }
        )
        self.fields["descripcion"].widget = forms.Textarea(
            attrs={
                "class": input_class,
                "rows": 4,
                "placeholder": "Descripción opcional de la sede",
            }
        )
        self.fields["imagen_referencia"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})
        self.fields["foto_pastor"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})

    class Meta:
        model = Sede
        fields = [
            "nombre",
            "imagen_referencia",
            "direccion",
            "ciudad",
            "telefono",
            "email",
            "pastor_responsable",
            "foto_pastor",
            "descripcion",
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


class CoordinadorForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="Nombre")
    last_name = forms.CharField(max_length=150, label="Apellido")
    username = forms.CharField(max_length=150, label="Usuario")
    email = forms.EmailField(label="Correo")
    cargo = forms.CharField(max_length=100, label="Cargo", initial="Coordinador")
    avatar = forms.ImageField(required=False, label="Foto")
    password1 = forms.CharField(widget=forms.PasswordInput(), label="Contraseña", required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(), label="Confirmar contraseña", required=False)
    is_active = forms.BooleanField(required=False, initial=True, label="Activo")

    def __init__(self, *args, admin_profile=None, **kwargs):
        self.admin_profile = admin_profile
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
        self.fields["first_name"].widget.attrs.update({"class": input_class})
        self.fields["last_name"].widget.attrs.update({"class": input_class})
        self.fields["username"].widget.attrs.update({"class": input_class})
        self.fields["email"].widget.attrs.update({"class": input_class})
        self.fields["cargo"].widget.attrs.update({"class": input_class})
        self.fields["avatar"].widget = forms.FileInput(attrs={"class": file_input_class, "accept": "image/*"})
        self.fields["password1"].widget.attrs.update({"class": input_class})
        self.fields["password2"].widget.attrs.update({"class": input_class})
        self.fields["is_active"].widget.attrs.update({"class": "h-4 w-4 rounded border-stone-400 text-stone-800 focus:ring-stone-300"})

    def clean_username(self):
        username = self.cleaned_data["username"]
        queryset = AdminEscuela._meta.get_field("user").remote_field.model.objects.filter(username=username)
        if self.admin_profile:
            queryset = queryset.exclude(pk=self.admin_profile.user_id)
        if queryset.exists():
            raise forms.ValidationError("Ese usuario ya existe.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        queryset = AdminEscuela._meta.get_field("user").remote_field.model.objects.filter(email=email)
        if self.admin_profile:
            queryset = queryset.exclude(pk=self.admin_profile.user_id)
        if queryset.exists():
            raise forms.ValidationError("Ese correo ya existe.")
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

        return cleaned_data

    def save(self, user_model, sede, hechos_module):
        data = self.cleaned_data

        if self.admin_profile:
            user = self.admin_profile.user
            user.first_name = data["first_name"]
            user.last_name = data["last_name"]
            user.username = data["username"]
            user.email = data["email"]
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
            self.admin_profile.cargo = data["cargo"]
            self.admin_profile.is_active = data["is_active"]
            self.admin_profile.save()
            admin_profile = self.admin_profile
        else:
            user = user_model.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password1"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role="app_admin",
                sede=sede,
                is_active=data["is_active"],
                is_staff=True,
                avatar=data.get("avatar"),
            )
            admin_profile = AdminEscuela.objects.create(
                user=user,
                sede=sede,
                cargo=data["cargo"],
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
