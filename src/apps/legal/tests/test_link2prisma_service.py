import pytest
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch, MagicMock
from apps.legal.services.link2prisma_service import Link2PrismaService


class TestLink2PrismaService(TestCase):
    def setUp(self):
        settings.LINK2PRISMA_PFX_PATH = '/path/to/test.pfx'
        settings.LINK2PRISMA_BASE_URL = 'https://test.link2prisma.com'

    @patch('requests.request')
    def test_make_request(self, mock_request):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        # Test API request
        result = Link2PrismaService._make_request(
            method="GET",
            endpoint="test/endpoint",
            data={"test": "data"}
        )

        # Verify request was made with correct parameters
        self.assertEqual(result, {"status": "success"})
        mock_request.assert_called_once()
        kwargs = mock_request.call_args[1]
        self.assertEqual(kwargs['method'], "GET")
        self.assertEqual(
            kwargs['url'],
            f"{settings.LINK2PRISMA_BASE_URL}/test/endpoint"
        )
        self.assertEqual(kwargs['json'], {"test": "data"})
        self.assertEqual(kwargs['cert'], settings.LINK2PRISMA_PFX_PATH)

    @patch('requests.request')
    def test_test_connection(self, mock_request):
        # Mock successful API response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response
        
        # Test successful connection
        self.assertTrue(Link2PrismaService.test_connection())

        # Test failed connection
        mock_request.side_effect = Exception("Connection failed")
        self.assertFalse(Link2PrismaService.test_connection())