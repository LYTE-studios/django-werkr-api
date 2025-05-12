from django.core.management.base import BaseCommand
from apps.authentication.models.user import User
from collections import defaultdict

class Command(BaseCommand):
    help = 'Reformats user emails to have lowercase first letter and identifies duplicates'

    def handle(self, *args, **options):
        # Get all users
        users = User.objects.all()
        self.stdout.write(f"Found {users.count()} users to process")

        # Dictionary to track emails and their users
        email_map = defaultdict(list)

        # First pass: Map all emails to their users
        for user in users:
            # Get the lowercase version of the email for comparison
            lowercase_email = user.email.lower()
            email_map[lowercase_email].append(user)

        # Track statistics
        processed_count = 0
        duplicate_count = 0
        modified_count = 0

        # Second pass: Process emails
        for lowercase_email, users_with_email in email_map.items():
            if len(users_with_email) > 1:
                # This is a duplicate case - print it out and don't modify
                duplicate_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"\nFound duplicate email accounts (keeping both unchanged):"
                    )
                )
                for user in users_with_email:
                    self.stdout.write(
                        f"  User ID: {user.id}, Email: {user.email}, "
                        f"Name: {user.first_name} {user.last_name}"
                    )
            else:
                # Single user case - lowercase first letter if needed
                user = users_with_email[0]
                if user.email[0].isupper():
                    old_email = user.email
                    user.email = user.email[0].lower() + user.email[1:]
                    user.save(update_fields=['email'])
                    modified_count += 1
                    self.stdout.write(
                        f"Updated email for user {user.id}: {old_email} -> {user.email}"
                    )
            
            processed_count += len(users_with_email)

        # Print summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nFinished processing emails:\n"
                f"Total users processed: {processed_count}\n"
                f"Users with duplicate emails: {duplicate_count * 2}\n"
                f"Users with modified emails: {modified_count}"
            )
        )