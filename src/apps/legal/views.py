from django.shortcuts import get_object_or_404
from django.db import models
from apps.jobs.models.application import JobApplication
from apps.jobs.models.dimona import Dimona
from rest_framework.views import APIView
from rest_framework import status
from datetime import datetime, timedelta

from .utils.contract_util import ContractUtil
from .services.link2prisma_service import Link2PrismaService
from apps.authentication.views import JWTBaseAuthView
from django.http import HttpRequest, HttpResponse
from rest_framework.response import Response
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import *
import uuid


class DownloadContractView(JWTBaseAuthView):
    """
    A view for workers to download their contract if their application is approved.
    """

    def post(self, request: HttpRequest, *args, **kwargs):
        # Initialize the formatter with the request kwargs
        formatter = FormattingUtil(kwargs)
        # Retrieve the application ID from the formatted kwargs
        application_id = formatter.get_value(value_key=k_id)

        # Fetch the JobApplication object or return a 404 if not found
        job_application = get_object_or_404(JobApplication, id=application_id)

        # Check if the job application is approved
        if not job_application.application_state == "approved":
            # Return a 400 response if the application is not approved
            return HttpResponse("Worker not approved", status=400)

        # Generate or get the contract path
        contract_path = ContractUtil.generate_contract(job_application)

        # Open and read the contract file
        with open(contract_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename=contract_{job_application.id}.pdf'
            return response


class DimonaDeclarationsView(JWTBaseAuthView):
    """
    A view for admin users to fetch the latest Dimona declarations from Link2Prisma API.
    This helps track the status of Dimona submissions for the admin team.
    """

    def get(self, request: HttpRequest, *args, **kwargs):
        """
        Fetch the latest Dimona declarations and their statuses from Link2Prisma.
        
        Query Parameters:
        - days: Number of days to look back (default: 7)
        - limit: Maximum number of records to return (default: 50)
        """
        try:
            # Get query parameters
            days_back = int(request.GET.get('days', 7))
            limit = int(request.GET.get('limit', 50))
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # Use Link2Prisma's bulk modifications endpoint for better performance
            # Format dates for Link2Prisma API (YYYYMMDD)
            start_date_str = start_date.strftime("%Y%m%d")
            end_date_str = end_date.strftime("%Y%m%d")
            
            # Get all modifications (including Dimona submissions) from Link2Prisma
            modifications_result = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'modifications/{start_date_str}/{end_date_str}'
            )
            
            # Get local Dimona records for cross-reference
            local_dimona_records = Dimona.objects.filter(
                models.Q(created__gte=start_date, created__lte=end_date) |
                models.Q(created__isnull=True)
            ).select_related('application', 'application__worker', 'application__job').order_by('-created')
            
            # Create a lookup dictionary for local records
            local_dimona_lookup = {dimona.id: dimona for dimona in local_dimona_records}
            
            # Prepare response data
            dimona_declarations = []
            
            # Process Link2Prisma modifications if available
            if modifications_result and isinstance(modifications_result, list):
                # Filter for Dimona-related modifications
                dimona_modifications = [
                    mod for mod in modifications_result
                    if mod.get('Type', '').lower() == 'dimona'
                ][:limit]
                
                for modification in dimona_modifications:
                    mod_id = modification.get('ID')
                    local_dimona = local_dimona_lookup.get(mod_id)
                    
                    if local_dimona:
                        # We have local record - combine with Link2Prisma data
                        declaration_data = {
                            'id': mod_id,
                            'created': local_dimona.created.isoformat() if local_dimona.created else None,
                            'local_success': local_dimona.success,
                            'local_reason': local_dimona.reason,
                            'application': {
                                'id': str(local_dimona.application.id),
                                'worker_name': f"{local_dimona.application.worker.first_name} {local_dimona.application.worker.last_name}",
                                'worker_ssn': local_dimona.application.worker.worker_profile.ssn,
                                'job_title': local_dimona.application.job.title,
                                'job_start': local_dimona.application.job.start_time.isoformat(),
                                'job_end': local_dimona.application.job.end_time.isoformat(),
                            },
                            'prisma_status': {
                                'action': modification.get('Action'),
                                'status_code': modification.get('Statuscode'),
                                'status_description': modification.get('StatusDescription'),
                                'type': modification.get('Type'),
                                'employer': modification.get('Employer'),
                                'worker': modification.get('Worker'),
                                'response': modification.get('Response', ''),
                                'processed': modification.get('Statuscode') not in ['400.05', '202']
                            }
                        }
                    else:
                        # Link2Prisma record without local record
                        declaration_data = {
                            'id': mod_id,
                            'created': None,
                            'local_success': None,
                            'local_reason': 'Record found in Link2Prisma but not in local database',
                            'application': None,
                            'prisma_status': {
                                'action': modification.get('Action'),
                                'status_code': modification.get('Statuscode'),
                                'status_description': modification.get('StatusDescription'),
                                'type': modification.get('Type'),
                                'employer': modification.get('Employer'),
                                'worker': modification.get('Worker'),
                                'response': modification.get('Response', ''),
                                'processed': modification.get('Statuscode') not in ['400.05', '202']
                            }
                        }
                    
                    dimona_declarations.append(declaration_data)
            
            else:
                # Fallback to local records only if Link2Prisma modifications endpoint fails
                prisma_api_error = None
                if modifications_result and isinstance(modifications_result, dict):
                    # Prisma responded with an error (permissions or similar)
                    prisma_api_error = {
                        'status_code': modifications_result.get('Statuscode'),
                        'status_description': modifications_result.get('StatusDescription'),
                        'action': modifications_result.get('Action'),
                        'response': modifications_result.get('Response'),
                        'id': modifications_result.get('ID')
                    }

                for dimona in local_dimona_records[:limit]:
                    declaration_data = {
                        'id': dimona.id,
                        'created': dimona.created.isoformat() if dimona.created else None,
                        'local_success': dimona.success,
                        'local_reason': dimona.reason,
                        'application': {
                            'id': str(dimona.application.id),
                            'worker_name': f"{dimona.application.worker.first_name} {dimona.application.worker.last_name}",
                            'worker_ssn': dimona.application.worker.worker_profile.ssn,
                            'job_title': dimona.application.job.title,
                            'job_start': dimona.application.job.start_time.isoformat(),
                            'job_end': dimona.application.job.end_time.isoformat(),
                        },
                        'prisma_status': None  # No Link2Prisma data available
                    }
                    dimona_declarations.append(declaration_data)

            
            # Prepare summary statistics
            total_declarations = len(dimona_declarations)
            processed_count = sum(1 for d in dimona_declarations
                                if d['prisma_status'] and d['prisma_status'].get('processed', False))
            pending_count = total_declarations - processed_count
            
            response_data = {
                'summary': {
                    'total_declarations': total_declarations,
                    'processed': processed_count,
                    'pending': pending_count,
                    'date_range': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat(),
                        'days': days_back
                    }
                },
                'declarations': dimona_declarations
            }
            # If Prisma batch access failed, return the API error info as well (not alarming, just info for admin)
            if 'prisma_api_error' in locals() and prisma_api_error:
                response_data['prisma_api_error'] = prisma_api_error
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response(
                {'error': 'Invalid query parameters', 'details': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch Dimona declarations', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DimonaDeclarationDetailView(JWTBaseAuthView):
    """
    A view to get detailed information about a specific Dimona declaration.
    """

    def get(self, request: HttpRequest, dimona_id: str, *args, **kwargs):
        """
        Get detailed information about a specific Dimona declaration.
        
        Args:
            dimona_id: The UniqueIdentifier of the Dimona declaration
        """
        try:
            # Get local Dimona record
            try:
                dimona = Dimona.objects.select_related(
                    'application', 'application__worker', 'application__job'
                ).get(id=dimona_id)
            except Dimona.DoesNotExist:
                return Response(
                    {'error': 'Dimona declaration not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get the latest status from Link2Prisma
            prisma_result = Link2PrismaService._make_request(
                method='GET',
                endpoint=f'Result/{dimona_id}'
            )
            
            # Prepare detailed response
            response_data = {
                'id': dimona.id,
                'created': dimona.created.isoformat() if dimona.created else None,
                'local_success': dimona.success,
                'local_reason': dimona.reason,
                'application': {
                    'id': str(dimona.application.id),
                    'state': dimona.application.application_state,
                    'worker': {
                        'id': str(dimona.application.worker.id),
                        'name': f"{dimona.application.worker.first_name} {dimona.application.worker.last_name}",
                        'email': dimona.application.worker.email,
                        'ssn': dimona.application.worker.worker_profile.ssn,
                        'worker_type': dimona.application.worker.worker_profile.worker_type,
                    },
                    'job': {
                        'id': str(dimona.application.job.id),
                        'title': dimona.application.job.title,
                        'description': dimona.application.job.description,
                        'start_time': dimona.application.job.start_time.isoformat(),
                        'end_time': dimona.application.job.end_time.isoformat(),
                        'location': {
                            'street': dimona.application.job.job_address.street_name,
                            'house_number': dimona.application.job.job_address.house_number,
                            'city': dimona.application.job.job_address.city,
                            'zip_code': dimona.application.job.job_address.zip_code,
                        }
                    }
                },
                'prisma_status': None
            }
            
            # Add Link2Prisma status if available
            if prisma_result and isinstance(prisma_result, dict):
                response_data['prisma_status'] = prisma_result
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {'error': 'Failed to fetch Dimona declaration details', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )