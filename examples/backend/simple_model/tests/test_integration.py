from testing.integration import RxIntegrationTestCase

from simple_model.models import User


class SimpleModelIntegrationTests(RxIntegrationTestCase):
    app_label = 'simple_model'
    channel = 'SimpleModelChannel'
    url = '/ws/simple_model/'

    def test_authorize_forwards_serialized_user_to_frontend(self):
        User.objects.update_or_create(
            id=1,
            defaults={'name': 'Registered User'},
        )
        self.eval('const authorized = await channel.authorize("password")')
        self.wait_for('channel.user !== null')
        state = self.get_result('{ authorized, user: channel.user }')

        self.assertEqual(
            state,
            {
                'authorized': True,
                'user': {'name': 'Registered User', '_loaded': True},
            },
        )
