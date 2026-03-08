from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0012_donationentry'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfitDistributionConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Configuracao de distribuicao de lucro',
                'verbose_name_plural': 'Configuracoes de distribuicao de lucro',
            },
        ),
        migrations.CreateModel(
            name='ProfitDistributionPerson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Pessoa da distribuicao de lucro',
                'verbose_name_plural': 'Pessoas da distribuicao de lucro',
                'ordering': ['name'],
            },
        ),
    ]
