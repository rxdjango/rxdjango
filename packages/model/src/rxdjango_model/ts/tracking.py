import os
import difflib
import subprocess
import types
import typing
from decimal import Decimal
from datetime import datetime
from django.db.models.query import QuerySet
from django.utils import timezone
from rest_framework import serializers

__serializers = set()

def export_interface(Serializer) -> None:
    """Mark this serializer so that its interface will be exported"""
    if issubclass(Serializer, serializers.Serializer):
        __serializers.add(_key(Serializer))
    return Serializer


def ts_exported(Serializer) -> bool:
    """Check if a serializer interface should be exported as TS"""
    return _key(Serializer) in __serializers


def _key(Serializer):
    return '.'.join([Serializer.__module__, Serializer.__name__])
