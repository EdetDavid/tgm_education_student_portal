from django.core.exceptions import DisallowedHost
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.hosts import allowed_hosts


class DeploymentHostTests(SimpleTestCase):
    def test_exact_deployment_hosts_are_allowed_without_trusting_other_tenants(self):
        deployment = 'tgm-student-portal-backend-hjvjfrm0r-edetdavids-projects.vercel.app'
        hosts = allowed_hosts({
            'DJANGO_ALLOWED_HOSTS': ' localhost, portal.example.com ',
            'VERCEL_URL': deployment,
            'VERCEL_PROJECT_PRODUCTION_URL': 'https://tgm-student-portal-backend.vercel.app',
        })
        with override_settings(ALLOWED_HOSTS=hosts):
            factory = RequestFactory()
            self.assertEqual(factory.get('/', HTTP_HOST=deployment).get_host(), deployment)
            self.assertEqual(factory.get('/', HTTP_HOST='portal.example.com').get_host(), 'portal.example.com')
            with self.assertRaises(DisallowedHost):
                factory.get('/', HTTP_HOST='unrelated.vercel.app').get_host()
