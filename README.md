# sitemissao

## Rodar localmente

```powershell
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_products
.\.venv\Scripts\python manage.py runserver
```

## Checkout Pix

Você pode definir a chave Pix usada no QR Code:

```powershell
$env:PIX_KEY="sua-chave-pix"
```

## Login para gerenciar produtos

Crie um usuário administrador:

```powershell
.\.venv\Scripts\python manage.py createsuperuser
```

## Imagem do cabeçalho

Coloque a imagem da missão neste caminho:

`static/shop/img/missao-andrews-cabecalho.jpg`
