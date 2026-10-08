from django.test import SimpleTestCase


class DeploymentTests(SimpleTestCase):
    def test_api_responses_are_not_shared_cacheable(self):
        response = self.client.get('/api/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertIn('private', response.headers['Cache-Control'])

    def test_csrf_cookie_response_is_not_cached(self):
        response = self.client.get('/api/admin/csrf/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
