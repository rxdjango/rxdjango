from django.db import models


class Company(models.Model):
    name = models.CharField(max_length=64)


class User(models.Model):
    name = models.CharField(max_length=32)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='users')
