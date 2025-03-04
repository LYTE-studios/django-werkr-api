import os
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from apps.jobs.models import JobApplication
from apps.core.utils.formatters import FormattingUtil
from django.core.files import File
import tempfile
from django.conf import settings

class ContractUtil:

    @staticmethod
    def get_context(application):
        start = FormattingUtil.to_user_timezone(application.job.start_time)
        end = FormattingUtil.to_user_timezone(application.job.end_time)

        start_time_morning = ''
        end_time_morning = ''

        start_time_afternoon = ''
        end_time_afternoon = ''

        if start.hour < 12:
            start_time_morning = FormattingUtil.to_readable_time(application.job.start_time)
            if end.hour < 12:
                end_time_morning = FormattingUtil.to_readable_time(application.job.end_time)
            else:
                end_time_morning = '12:00'
        else:
            start_time_afternoon = FormattingUtil.to_readable_time(application.job.start_time)
            end_time_afternoon = FormattingUtil.to_readable_time(application.job.end_time)

        weekday = FormattingUtil.to_day_of_the_week(application.job.start_time)

        start_date = FormattingUtil.to_date(application.job.start_time)
        end_date = FormattingUtil.to_date(application.job.end_time)
        duration = FormattingUtil.to_readable_duration(application.job.end_time - application.job.start_time, )

        name = application.worker.first_name + " " + application.worker.last_name

        address = ''

        if application.worker.worker_profile.worker_address is not None:
            address = application.worker.worker_profile.worker_address.to_readable()

        birth_date = None

        if application.worker.worker_profile.date_of_birth is not None:
            birth_date = FormattingUtil.to_full_date(application.worker.worker_profile.date_of_birth)

        signature_path = os.path.join(settings.BASE_DIR, 'templates', 'contracts', 'signature.png')

        return {
            'name': name,
            'address': address,
            'birth_date': birth_date,
            'iban': application.worker.worker_profile.iban,
            'weekday': weekday,
            'start_date': start_date,
            'end_date': end_date,
            'start_time_morning': start_time_morning,
            'end_time_morning': end_time_morning,
            'start_time_afternoon': start_time_afternoon,
            'end_time_afternoon': end_time_afternoon,
            'duration': duration,
            'signature_path': signature_path,
        }
    

    @staticmethod
    def generate_contract(application: JobApplication):

        def get_path(contract_name: str):
            return os.path.join('contracts', contract_name +  '.html')

        template_mapping = {
            ('121', 'freelancer'): get_path('contract_automotive_freelance'),
            ('121', 'student'): get_path('contract_automotive_student'),
            ('302', 'freelancer'): get_path('contract_horeca_freelance'),
            ('302', 'student'): get_path('contract_horeca_student'),
            ('302', 'flexi'): get_path('contract_horeca_flexi'),
            ('121h', 'freelancer'): get_path('contract_hospitality_freelance'),
            ('121h', 'student'): get_path('contract_hospitality_student'),
        }

        template_name = template_mapping.get((application.job.customer.customer_profile.special_committee or '121', application.worker.worker_profile.worker_type or 'student'))

        if not template_name:
            raise ValueError("No contract template found for the given combination.")

        context = ContractUtil.get_context(application)

        try:
            html_string = render_to_string(template_name, context)
        except Exception as e:
            print(e, type(e))
            raise e
        contract_path = os.path.join('media', f'{application.id}_contract.pdf')

        with open(contract_path, 'w+b') as result_file:
            pisa_status = pisa.CreatePDF(html_string, dest=result_file)
            if pisa_status.err:
                raise print(str(pisa_status.err))
            
        with open(contract_path, 'rb') as result_file:
            django_file = File(result_file)
            application.contract.save(f'{application.id}_contract.pdf', django_file, save=True)
    
            os.remove(contract_path)
