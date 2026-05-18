from django import forms
from .models import Feed, Category, Medio, SiteConfig


class FeedForm(forms.ModelForm):
    class Meta:
        model = Feed
        fields = ['name', 'url', 'medio', 'category', 'is_active', 'blocked_keywords']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del feed'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://ejemplo.com/rss'}),
            'medio': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'blocked_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: patrocinado, publicidad, sorteo',
            }),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la categoría'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'slug-url (dejar vacío para autogenerar)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False


class MedioForm(forms.ModelForm):
    class Meta:
        model = Medio
        fields = ['name', 'slug', 'favicon_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del medio'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'slug-url (dejar vacío para autogenerar)'}),
            'favicon_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://ejemplo.com/favicon.ico (opcional, se detecta automáticamente)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['favicon_url'].required = False


class SiteConfigForm(forms.ModelForm):
    class Meta:
        model = SiteConfig
        fields = ['theme', 'articles_retention_days']
        widgets = {
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'articles_retention_days': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 365,
            }),
        }
        labels = {
            'theme': 'Modo de color',
            'articles_retention_days': 'Días de retención de noticias',
        }
        help_texts = {
            'articles_retention_days': 'Las noticias con más de este número de días se eliminarán automáticamente.',
        }
