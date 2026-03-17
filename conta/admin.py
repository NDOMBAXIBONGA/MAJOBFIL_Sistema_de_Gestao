from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Conta
from .forms import ContaCreationForm

class ContaAdmin(UserAdmin):
    add_form = ContaCreationForm
    model = Conta
    
    list_display = ('email', 'username', 'nome', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'provincia')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': (
            'username', 'nome', 'telemovel', 'data_nascimento', 'bilhete_identidade'
        )}),
        ('Localização', {'fields': ('bairro', 'cidade', 'provincia', 'municipio')}),
        ('Permissões', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'username', 'nome', 'password1', 'password2',
                'telemovel', 'data_nascimento', 'bilhete_identidade',
                'bairro', 'cidade', 'provincia', 'municipio', 'is_staff', 'is_active', 'is_superuser'
            )}
        ),
    )
    
    search_fields = ('email', 'username', 'nome')
    ordering = ('email',)

admin.site.register(Conta, ContaAdmin)