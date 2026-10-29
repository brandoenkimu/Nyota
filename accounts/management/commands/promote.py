"""python manage.py promote <username-or-email> --role admin

Gives an existing account (for example one made with `createsuperuser` before this command existed)
a Nyota role, so it can sign in at the right door."""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from accounts.models import User


class Command(BaseCommand):
    help = 'Set the role of an existing user.'

    def add_arguments(self, p):
        p.add_argument('who')
        p.add_argument('--role', default='admin', choices=['admin', 'analyst', 'developer', 'ceo', 'support', 'customer'])

    def handle(self, *a, **o):
        user = User.objects.filter(Q(username__iexact=o['who']) | Q(email__iexact=o['who'])).first()
        if not user:
            raise CommandError('No such user.')
        user.role = o['role']
        user.email_verified = True
        user.save(update_fields=['role', 'email_verified'])
        door = '/login/' if o['role'] == 'customer' else '/staff/login/'
        self.stdout.write(self.style.SUCCESS(f'{user.username} is now {o["role"]}. Sign in at {door}'))
