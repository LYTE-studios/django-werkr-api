import os
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from apps.jobs.models import JobApplication
from apps.core.utils.formatters import FormattingUtil


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

        if application.worker.address is not None:
            address = application.worker.address.to_readable()

        birth_date = None

        if application.worker.date_of_birth is not None:
            birth_date = FormattingUtil.to_full_date(application.worker.date_of_birth)

        return {
            'name': name,
            'address': address,
            'birth_date': birth_date,
            'iban': application.worker.tax_number,
            'weekday': weekday,
            'start_date': start_date,
            'end_date': end_date,
            'start_time_morning': start_time_morning,
            'end_time_morning': end_time_morning,
            'start_time_afternoon': start_time_afternoon,
            'end_time_afternoon': end_time_afternoon,
            'duration': duration,
        }

    @staticmethod
    def generate_contract(application: JobApplication):
        template_mapping = {
            ('121', 'freelancer'): os.path.join('contracts', 'contract_automotive_freelance.html'),
            ('121', 'student'): os.path.join('contracts', 'contract_automotive_student.html'),
            ('302', 'student'): os.path.join('contracts', 'contract_horeca_flexi.html'),
            ('302', 'flexi'): os.path.join('contracts', 'contract_horeca_freelance.html'),
            ('302', 'freelancer'): os.path.join('contracts', 'contract_horeca_student.html'),
            ('121h', 'freelancer'): os.path.join('contracts', 'contract_hospitality_freelance.html'),
            ('121h', 'student'): os.path.join('contracts', 'contract_hospitality_student.html'),
        }

        template_name = template_mapping.get((application.customer.customer_profile.special_committee, application.worker.worker_profile.worker_type))

        if not template_name:
            raise ValueError("No contract template found for the given combination.")

        context = ContractUtil.get_context(application)

        html_string = render_to_string(template_name, context)
        contract_path = os.path.join('media', f'{application.id}_contract.pdf')

        with open(contract_path, 'w+b') as result_file:
            pisa_status = pisa.CreatePDF(html_string, dest=result_file)
            if pisa_status.err:
                raise print(str(pisa_status.err))
            
            application.contract = result_file
            application.save()

            os.remove(contract_path)
