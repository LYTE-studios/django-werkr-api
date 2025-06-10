from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.legal.services.link2prisma_service import Link2PrismaService
from tabulate import tabulate
from typing import List, Dict, Any

User = get_user_model()

class Command(BaseCommand):
    help = 'Fetch worker records from Link2Prisma service'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ssn',
            type=str,
            help='Fetch a specific worker by SSN'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fetch all workers'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['table', 'json'],
            default='table',
            help='Output format (default: table)'
        )

    def handle(self, *args, **options):
        if not options['all'] and not options['ssn']:
            self.stdout.write(
                self.style.ERROR('Please provide either --ssn or --all option')
            )
            return

        try:
            if not settings.LINK2PRISMA_BASE_URL:
                self.stdout.write(
                    self.style.ERROR('LINK2PRISMA_BASE_URL not configured in settings')
                )
                return

            if not settings.LINK2PRISMA_EMPLOYER_REF:
                self.stdout.write(
                    self.style.ERROR('LINK2PRISMA_EMPLOYER_REF not configured in settings')
                )
                return

            if not settings.LINK2PRISMA_PFX_PATH:
                self.stdout.write(
                    self.style.ERROR('LINK2PRISMA_PFX_PATH not configured in settings')
                )
                return

            # Test connection first
            try:
                Link2PrismaService.test_connection()
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Connection error: {str(e)}')
                )
                return

            if options['ssn']:
                self.fetch_single_worker(options['ssn'], options['format'])
            else:
                self.fetch_all_workers(options['format'])

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching worker data: {str(e)}')
            )
            self.stdout.write(
                self.style.WARNING('Make sure all required settings are configured:')
            )
            self.stdout.write('- LINK2PRISMA_BASE_URL')
            self.stdout.write('- LINK2PRISMA_EMPLOYER_REF')
            self.stdout.write('- LINK2PRISMA_PFX_PATH')

    def fetch_single_worker(self, ssn: str, output_format: str):
        """Fetch and display a single worker's data"""
        worker_data = Link2PrismaService.fetch_worker(ssn)
        
        if not worker_data:
            self.stdout.write(
                self.style.WARNING(f'No worker found with SSN: {ssn}')
            )
            return

        if output_format == 'json':
            self.display_json([worker_data])
        else:
            self.display_table([worker_data])

    def fetch_all_workers(self, output_format: str):
        """Fetch and display all workers' data"""
        # Get all active workers with worker profiles
        users = User.objects.filter(
            is_active=True,
            worker_profile__isnull=False
        ).select_related('worker_profile')

        worker_data = []
        for user in users:
            data = Link2PrismaService.fetch_worker(user.worker_profile.ssn)
            if data:
                worker_data.append(data)

        if not worker_data:
            self.stdout.write(
                self.style.WARNING('No worker data found')
            )
            return

        if output_format == 'json':
            self.display_json(worker_data)
        else:
            self.display_table(worker_data)

    def display_table(self, worker_data: List[Dict[str, Any]]):
        """Display worker data in a formatted table"""
        # Extract relevant fields for display
        headers = [
            'Worker Number',
            'Name',
            'SSN',
            'Status',
            'Last Sync',
            'Contract Type',
            'Working Time',
            'Student'
        ]
        rows = []
        
        for worker in worker_data:
            # Get the latest contract info if available
            contract = worker.get('contract', [{}])[0] if worker.get('contract') else {}
            
            rows.append([
                worker.get('WorkerNumber', 'N/A'),
                f"{worker.get('Firstname', '')} {worker.get('Name', '')}".strip(),
                worker.get('INSS', 'N/A'),
                worker.get('Status', 'N/A'),
                worker.get('LastSync', 'N/A'),
                contract.get('Contract', 'N/A'),
                contract.get('WorkingTime', 'N/A'),
                'Yes' if contract.get('Student', {}).get('Exist') == 'Y' else 'No'
            ])

        # Display table
        self.stdout.write(
            tabulate(
                rows,
                headers=headers,
                tablefmt='grid'
            )
        )
        self.stdout.write(f"\nTotal workers: {len(rows)}")

    def display_json(self, worker_data: List[Dict[str, Any]]):
        """Display worker data in JSON format"""
        import json
        self.stdout.write(
            json.dumps(worker_data, indent=2)
        )
        self.stdout.write(f"\nTotal workers: {len(worker_data)}")