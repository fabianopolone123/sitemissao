from django.core.management.base import BaseCommand

from shop.models import Product


class Command(BaseCommand):
    help = 'Popula o catalogo inicial com pasteis e combos missionarios.'

    def handle(self, *args, **options):
        Product.objects.update(active=False)

        products = [
            {
                'name': 'Pastel Queijo, Tomate e Oregano',
                'description': 'Pastel artesanal recheado com queijo, tomate e oregano.',
                'cause': 'Cantina Missionaria',
                'price': '12.00',
                'image_url': 'https://images.unsplash.com/photo-1621852004158-f3bc188ace2d?auto=format&fit=crop&w=900&q=80',
            },
            {
                'name': 'Pastel Queijo, Milho e PVT',
                'description': 'Pastel artesanal com queijo, milho e proteina vegetal texturizada.',
                'cause': 'Cantina Missionaria',
                'price': '12.00',
                'image_url': 'https://images.unsplash.com/photo-1608039829572-78524f79c4c7?auto=format&fit=crop&w=900&q=80',
            },
            {
                'name': 'Combo Pastel QTO + Suco',
                'description': '1 pastel queijo, tomate e oregano + 1 suco.',
                'cause': 'Cantina Missionaria',
                'price': '15.00',
                'image_url': 'https://images.unsplash.com/photo-1613478223719-2ab802602423?auto=format&fit=crop&w=900&q=80',
            },
            {
                'name': 'Combo Pastel QTO + Guarana',
                'description': '1 pastel queijo, tomate e oregano + 1 guarana.',
                'cause': 'Cantina Missionaria',
                'price': '15.00',
                'image_url': 'https://images.unsplash.com/photo-1622480916113-f2f5b8f4e5cb?auto=format&fit=crop&w=900&q=80',
            },
            {
                'name': 'Combo Pastel QMP + Suco',
                'description': '1 pastel queijo, milho e PVT + 1 suco.',
                'cause': 'Cantina Missionaria',
                'price': '15.00',
                'image_url': 'https://images.unsplash.com/photo-1532635241-17e820acc59f?auto=format&fit=crop&w=900&q=80',
            },
            {
                'name': 'Combo Pastel QMP + Guarana',
                'description': '1 pastel queijo, milho e PVT + 1 guarana.',
                'cause': 'Cantina Missionaria',
                'price': '15.00',
                'image_url': 'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?auto=format&fit=crop&w=900&q=80',
            },
        ]

        for data in products:
            Product.objects.update_or_create(
                name=data['name'],
                defaults={**data, 'active': True},
            )

        self.stdout.write(self.style.SUCCESS('Catalogo de pasteis atualizado com sucesso.'))
