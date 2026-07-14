"""Protocol-level test for the nested_model channel.

Verifies that the rx update for the ``user`` field arrives as two layered
frames -- one per instance type, parent-before-child (ADR-0016) -- rather
than either the pre-ADR-0010 nested-blob form or a single monolithic frame
carrying every layer at once.
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
        # One frame per layer, parent-before-child: the user frame precedes
        # the company frame it references.
        self.assertEqual(len(rx_frames), 2)
        user_frame, company_frame = [frame['data']['v'] for frame in rx_frames]

        self.assertIsInstance(user_frame, list)
        self.assertEqual(len(user_frame), 1)
        self.assertIsInstance(company_frame, list)
        self.assertEqual(len(company_frame), 1)

        user_layer = user_frame[0]
        company_layer = company_frame[0]
        self.assertEqual(user_layer['_type'], 'nested_model.serializers.UserSerializer')
        self.assertEqual(company_layer['_type'], 'nested_model.serializers.CompanySerializer')
        self.assertEqual(user_layer['name'], 'Registered User')
        self.assertEqual(user_layer['company'], company_layer['id'])
        self.assertEqual(company_layer['name'], 'Lorem Ipsum Inc')
