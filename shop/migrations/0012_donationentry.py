from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0011_auditlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='DonationEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=160)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
