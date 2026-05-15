from .fields import RxModelField, install_model_field, tracked_serializers
from .ts.models import install_typescript_hooks


install_model_field()
install_typescript_hooks()

__all__ = [
    'RxModelField',
    'tracked_serializers',
]
