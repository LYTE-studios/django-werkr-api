import os
from django.template.loader import render_to_string
from xhtml2pdf import pisa


def generate_contract(customer_profile, worker_profile):
    template_mapping = {
        ('121', 'freelancer'): os.path.join('contracts', 'contract_automotive_freelance.html'),
        ('121', 'student'):  os.path.join('contracts', 'contract_automotive_student.html'),
        ('302', 'student'):  os.path.join('contracts', 'contract_horeca_flexi.html'),
        ('302', 'flexi'): os.path.join('contracts', 'contract_horeca_freelance.html'),
        ('302', 'freelancer'): os.path.join('contracts', 'contract_horeca_student.html'),
        ('121h', 'freelancer'): os.path.join('contracts', 'contract_hospitality_freelance.html'),
        ('121h', 'student'): os.path.join('contracts', 'contract_hospitality_student.html'),
    }

    template_name = template_mapping.get((customer_profile.special_committee, worker_profile.worker_type))
    if not template_name:
        raise ValueError("No contract template found for the given combination.")

    context = {
        'customer_profile': customer_profile,
        'worker_profile': worker_profile,
    }

    html_string = render_to_string(template_name, context)
    contract_path = os.path.join('media', f'{worker_profile.user.id}_contract.pdf')

    with open(contract_path, 'w+b') as result_file:
        pisa_status = pisa.CreatePDF(html_string, dest=result_file)
        if pisa_status.err:
            raise print(str(pisa_status.err))

    return contract_path
