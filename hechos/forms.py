from django import forms

from hechos.models import Ofrenda, QuejaReclamo


class QuejaReclamoForm(forms.ModelForm):
    class Meta:
        model = QuejaReclamo
        fields = ["tipo", "asunto", "mensaje"]
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
        self.fields["tipo"].widget.attrs.update({"class": input_class})
        self.fields["asunto"].widget.attrs.update({"class": input_class})
        self.fields["mensaje"].widget.attrs.update({"class": input_class})


class OfrendaForm(forms.ModelForm):
    class Meta:
        model = Ofrenda
        fields = ["valor"]  # "escuela" se agrega dinámicamente si hace falta
        labels = {
            "valor": "Valor",
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
        self.fields["valor"].widget.attrs.update({"class": input_class, "placeholder": "0.00"})

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")
        if valor is None:
            return valor
        if valor <= 0:
            raise forms.ValidationError("El valor debe ser mayor a 0.")
        return valor

