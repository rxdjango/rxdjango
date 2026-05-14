"""Protocol-level test for the nested_model channel.

Verifies that the rx update for the ``user`` field carries the flat
``[User, Company]`` layer pair produced by the backend ``StateModel``,
not the previous nested-blob form.
"""

from __future__ import annotations

from testing.integration import RxProtocolTestCase

from nested_model.models import Company, User


class NestedModelProtocolTests(RxProtocolTestCase):
    app_label = 'nested_model'
    channel = 'NestedModelChannel'
    url = '/ws/nested_model/'

    def test_update_message_carries_two_flat_dicts(self):
        company, _ = Company.objects.update_or_create(
            id=1, defaults={'name': 'Lorem Ipsum Inc'},
        )
        User.objects.update_or_create(
            id=1, defaults={'name': 'Registered User', 'company': company},
        )

        self.eval('await channel.authorize("password")')
        self.wait_for('channel.user !== null')
        self.get_trace()

        rx_frames = [
            entry for entry in self.last_trace
            if entry['from'] == 'server'
            and isinstance(entry['data'], dict)
            and entry['data'].get('t') == 'rx'
            and entry['data'].get('f') == 'user'
        ]
        self.assertEqual(len(rx_frames), 1)
        payload = rx_frames[0]['data']['v']

        self.assertIsInstance(payload, list)
        self.assertEqual(len(payload), 2)

        by_type = {entry['_type']: entry for entry in payload}
        self.assertIn('nested_model.serializers.UserSerializer', by_type)
        self.assertIn('nested_model.serializers.CompanySerializer', by_type)

        user_layer = by_type['nested_model.serializers.UserSerializer']
        company_layer = by_type['nested_model.serializers.CompanySerializer']
        self.assertEqual(user_layer['name'], 'Registered User')
        self.assertEqual(user_layer['company'], company_layer['id'])
        self.assertEqual(company_layer['name'], 'Lorem Ipsum Inc')
