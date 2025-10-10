from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('get-preco-convenio/', views.get_preco_convenio, name='get_preco_convenio'),
    path('get-preco-produto/', views.get_preco_produto, name='get_preco_produto'),
]