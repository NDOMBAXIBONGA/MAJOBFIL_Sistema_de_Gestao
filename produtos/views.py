# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from .models import Produto, Recarga
from .forms import ProdutoForm, RecargaForm, ItemForm

@login_required
@user_passes_test(lambda u: u.is_superuser)
def cadastrar_item(request):
    """View para cadastrar novo produto ou recarga"""
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            tipo_item = form.cleaned_data['tipo_item']
            nome = form.cleaned_data['nome']
            preco = form.cleaned_data['preco']
            imagem = form.cleaned_data['imagem']
            
            print(f"Tipo selecionado: {tipo_item}")  # Para debug
            
            if tipo_item == 'produto':
                # Salvar como Produto usando o ModelForm correto
                produto_form = ProdutoForm(request.POST, request.FILES)
                if produto_form.is_valid():
                    produto = produto_form.save()
                    messages.success(request, f'Produto "{produto.nome}" cadastrado com sucesso!')
                    return redirect('listar_todos_itens')
                else:
                    # Se houver erro no ProdutoForm, mostrar erros
                    for field, errors in produto_form.errors.items():
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
            else:
                # Salvar como Recarga usando o ModelForm correto
                recarga_form = RecargaForm(request.POST, request.FILES)
                if recarga_form.is_valid():
                    recarga = recarga_form.save()
                    messages.success(request, f'Recarga "{recarga.nome}" cadastrada com sucesso!')
                    return redirect('listar_todos_itens')
                else:
                    # Se houver erro no RecargaForm, mostrar erros
                    for field, errors in recarga_form.errors.items():
                        for error in errors:
                            messages.error(request, f'{field}: {error}')
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = ItemForm()
    
    context = {
        'form': form,
        'user': request.user
    }
    return render(request, 'cadastrar_item.html', context)

# views.py
@login_required
def listar_todos_itens(request):
    """View para listar todos os itens (produtos e recargas) juntos"""
    produtos = Produto.objects.all().order_by('nome')
    recargas = Recarga.objects.all().order_by('nome')
    
    context = {
        'produtos': produtos,
        'recargas': recargas,
        'user': request.user
    }
    return render(request, 'listar_todos_itens.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def deletar_item(request, item_id, item_type):
    """View unificada para deletar produto ou recarga"""
    if item_type == 'produto':
        item = get_object_or_404(Produto, id=item_id)
        redirect_url = 'listar_todos_itens'
    elif item_type == 'recarga':
        item = get_object_or_404(Recarga, id=item_id)
        redirect_url = 'listar_todos_itens'
    else:
        messages.error(request, 'Tipo de item inválido.')
        return redirect('listar_todos_itens')
    
    if request.method == 'POST':
        item_nome = item.nome
        item.delete()
        messages.success(request, f'Item "{item_nome}" deletado com sucesso!')
        return redirect(redirect_url)
    
    context = {
        'item': item,
        'item_type': item_type,
        'user': request.user
    }
    return render(request, 'deletar_item.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def editar_item(request, item_id, item_type):
    """View unificada para editar produto ou recarga"""
    if item_type == 'produto':
        item = get_object_or_404(Produto, id=item_id)
        FormClass = ProdutoForm
        redirect_url = 'listar_todos_itens'
    elif item_type == 'recarga':
        item = get_object_or_404(Recarga, id=item_id)
        FormClass = RecargaForm
        redirect_url = 'listar_todos_itens'
    else:
        messages.error(request, 'Tipo de item inválido.')
        return redirect('listar_todos_itens')
    
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save()
            messages.success(request, f'Item "{item.nome}" atualizado com sucesso!')
            return redirect(redirect_url)
        else:
            messages.error(request, 'Por favor, corrija os erros abaixo.')
    else:
        form = FormClass(instance=item)
    
    context = {
        'form': form,
        'item': item,
        'item_type': item_type,
        'user': request.user
    }
    return render(request, 'editar_item.html', context)