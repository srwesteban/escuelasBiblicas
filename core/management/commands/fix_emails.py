from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Corrige los emails de usuarios que contienen guiones bajos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué emails serían corregidos sin cambiarlos realmente'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Obtener usuarios con emails que contienen guiones bajos
        users_with_underscore_emails = User.objects.filter(email__contains='_')
        
        if not users_with_underscore_emails.exists():
            self.stdout.write(
                self.style.SUCCESS('✅ No hay emails con guiones bajos para corregir')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'🔍 Encontrados {users_with_underscore_emails.count()} usuarios con emails con guiones bajos:')
        )
        
        for user in users_with_underscore_emails:
            old_email = user.email
            new_email = old_email.replace('_', '')
            self.stdout.write(f'  - {user.username}: {old_email} → {new_email}')
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS('\n🔍 Modo dry-run: No se modificaron emails')
            )
            return
        
        # Confirmar cambios
        confirm = input('\n¿Estás seguro de que quieres corregir estos emails? (yes/no): ')
        if confirm.lower() != 'yes':
            self.stdout.write(
                self.style.WARNING('❌ Operación cancelada')
            )
            return
        
        # Corregir emails
        corrected_count = 0
        
        for user in users_with_underscore_emails:
            old_email = user.email
            new_email = old_email.replace('_', '')
            user.email = new_email
            user.save()
            corrected_count += 1
            self.stdout.write(f'  ✅ Corregido: {user.username} - {old_email} → {new_email}')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Se corrigieron {corrected_count} emails')
        )
        
        # Mostrar usuarios actualizados
        self.stdout.write(
            self.style.SUCCESS(f'\n📊 Usuarios con emails corregidos:')
        )
        
        for user in users_with_underscore_emails:
            self.stdout.write(f'  - {user.username}: {user.email}')
