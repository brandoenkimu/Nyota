"""python manage.py create_staff --role admin --first Jane --last Kamau --personal-email jane@gmail.com

Creates a platform staff account the same way the Administrator portal does: the username and company
e-mail are generated from the name and position (jane.kamau.admin@nyota.market), a temporary password
is generated and printed once, and the person must change it at first sign-in at /staff/login/."""
from django.core.management.base import BaseCommand, CommandError

from accounts.forms import StaffCreateForm
from accounts.models import User


class Command(BaseCommand):
    help = 'Create an admin, analyst, developer, ceo or support account from the command line.'

    def add_arguments(self, p):
        p.add_argument('--role', required=True, choices=['admin', 'analyst', 'developer', 'ceo', 'support'])
        p.add_argument('--first', required=True)
        p.add_argument('--last', required=True)
        p.add_argument('--personal-email', required=True, help='where the sign-in details are sent (not the login)')
        p.add_argument('--phone', default='')
        p.add_argument('--password', default='', help='choose the password instead of generating one')
        p.add_argument('--keep-password', action='store_true', help='do not force a password change at first sign-in')

    def handle(self, *a, **o):
        form = StaffCreateForm({'first_name': o['first'], 'last_name': o['last'], 'position': o['role'],
                                'personal_email': o['personal_email'], 'phone': o['phone']})
        if not form.is_valid():
            raise CommandError(form.errors.as_text())
        user, password = form.save(created_by=None)
        if o['password']:
            password = o['password']
            user.set_password(password)
        if o['keep_password']:
            user.must_change_password = False
        user.save()
        self.stdout.write(self.style.SUCCESS('Account created. Sign in at /staff/login/'))
        self.stdout.write(f'  Email (login): {user.email}\n  Username:      {user.username}\n  Password:      {password}')
