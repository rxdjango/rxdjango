"""End-to-end browser test for the nested_model example."""

from __future__ import annotations

from playwright.sync_api import expect

from testing.e2e import RxE2ETestCase

from nested_model.models import Company, User


class NestedModelE2ETests(RxE2ETestCase):
    def setUp(self):
        # Seed the test database before super().setUp() starts Playwright;
        # once Playwright's sync_api event loop is attached to this thread,
        # Django blocks ORM calls as ``SynchronousOnlyOperation``.
        company, _ = Company.objects.update_or_create(
            id=1, defaults={'name': 'Lorem Ipsum Inc'},
        )
        User.objects.update_or_create(
            id=1, defaults={'name': 'Registered User', 'company': company},
        )
        super().setUp()

    def test_company_name_renders_after_authorization(self):
        page = self.goto_demo('examples/nested_model')

        page.get_by_role('button', name='Authorize').click()

        expect(page.get_by_text('Lorem Ipsum Inc')).to_be_visible()
