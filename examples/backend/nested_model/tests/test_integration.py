from testing.integration import RxIntegrationTestCase

from nested_model.models import Company, User


class NestedModelIntegrationTests(RxIntegrationTestCase):
    app_label = 'nested_model'
    channel = 'NestedModelChannel'
    url = '/ws/nested_model/'

    def test_company_name_appears_in_rebuilt_state(self):
        company, _ = Company.objects.update_or_create(
            id=1, defaults={'name': 'Lorem Ipsum Inc'},
        )
        User.objects.update_or_create(
            id=1, defaults={'name': 'Registered User', 'company': company},
        )

        self.eval('await channel.authorize("password")')
        self.wait_for('channel.user !== null')
        company_name = self.get_result('channel.user.company.name')

        self.assertEqual(company_name, 'Lorem Ipsum Inc')
