# Instruções de Deploy para o Servidor

## Informações
- **Repositório**: https://github.com/cfricarte/compufour.git
- **Servidor**: root@srv1057071
- **Diretório de destino**: /usr/local/lsws/Example/html/demo

## Passos para Deploy

### 1. Conectar ao servidor via SSH
```bash
ssh root@srv1057071
```

### 2. Navegar até o diretório de destino
```bash
cd /usr/local/lsws/Example/html/demo
```

### 3. Fazer backup do diretório atual (recomendado)
```bash
cd /usr/local/lsws/Example/html
mv demo demo_backup_$(date +%Y%m%d_%H%M%S)
```

### 4. Clonar o repositório
```bash
cd /usr/local/lsws/Example/html
git clone https://github.com/cfricarte/compufour.git demo
```

**OU** se o diretório demo já existe e você quer sobrescrever:

### 4 (Alternativo). Remover diretório existente e clonar
```bash
cd /usr/local/lsws/Example/html
rm -rf demo
git clone https://github.com/cfricarte/compufour.git demo
```

### 5. Configurar permissões
```bash
cd /usr/local/lsws/Example/html/demo
chown -R nobody:nogroup .
chmod -R 755 .
```

### 6. Instalar dependências Python
```bash
cd /usr/local/lsws/Example/html/demo

# Criar ambiente virtual (se não existir)
python3 -m venv venv

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 7. Configurar banco de dados
```bash
# Aplicar migrações
python manage.py migrate

# Criar superusuário (se necessário)
python manage.py createsuperuser

# Coletar arquivos estáticos
python manage.py collectstatic --noinput
```

### 8. Reiniciar o servidor web (LiteSpeed)
```bash
systemctl restart lsws
# OU
/usr/local/lsws/bin/lswsctrl restart
```

## Comandos Rápidos para Atualizar (depois do primeiro deploy)

Se você já tem o repositório clonado e quer apenas atualizar:

```bash
cd /usr/local/lsws/Example/html/demo
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart lsws
```

## Configurações Importantes

### Arquivo settings.py
Certifique-se de que o `settings.py` está configurado corretamente para produção:

```python
# Em produção, defina:
DEBUG = False
ALLOWED_HOSTS = ['72.60.253.150', 'r3sys.com.br', 'www.r3sys.com.br']

# Configure arquivos estáticos
STATIC_ROOT = '/usr/local/lsws/Example/html/demo/staticfiles/'
STATIC_URL = '/static/'
```

### Variáveis de Ambiente (Recomendado)
Crie um arquivo `.env` para armazenar informações sensíveis:

```bash
nano /usr/local/lsws/Example/html/demo/.env
```

Conteúdo do arquivo `.env`:
```
SECRET_KEY=sua_chave_secreta_aqui
DEBUG=False
ALLOWED_HOSTS=72.60.253.150,r3sys.com.br,www.r3sys.com.br
DATABASE_URL=sqlite:///db.sqlite3
```

## Troubleshooting

### Permissões
Se tiver problemas com permissões:
```bash
cd /usr/local/lsws/Example/html/demo
chown -R nobody:nogroup .
chmod -R 755 .
chmod 664 db.sqlite3
```

### Logs
Verificar logs do LiteSpeed:
```bash
tail -f /usr/local/lsws/logs/error.log
```

### Verificar Status
```bash
systemctl status lsws
```

## Notas de Segurança

1. **Nunca commit a SECRET_KEY** - Use variáveis de ambiente
2. **DEBUG = False** em produção
3. **Mantenha o db.sqlite3 fora do controle de versão** (adicione ao .gitignore)
4. **Use HTTPS** em produção
5. **Configure CORS** se necessário
6. **Proteja arquivos sensíveis** com permissões adequadas

## Estrutura de Diretórios Esperada

```
/usr/local/lsws/Example/html/demo/
├── compufour/
├── core/
├── templates/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── venv/
└── staticfiles/ (após collectstatic)
```
