# middleware/force_custom_errors.py
from django.http import HttpResponseNotFound
from django.shortcuts import render
import re

class ForceCustomErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Se for uma resposta 404 e DEBUG=True, mostra template personalizado
        if response.status_code == 404:
            # Verifica se é uma URL que não existe (não é arquivo estático)
            if not re.match(r'^/static/|^/media/|^/favicon\.ico$', request.path):
                return render(request, '404.html', {
                    'request_path': request.path
                }, status=404)
        
        return response