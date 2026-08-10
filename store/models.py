from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


# Canonical categories used across seed data, CSV import, and API validation.
PRODUCT_CATEGORIES = [
    'Electronics',
    'Fashion',
    'Books',
    'Furniture',
    'Gaming',
    'Education',
    'Misc',
]


def validate_product_category(value):
    if value not in PRODUCT_CATEGORIES:
        raise ValidationError(
            f'Invalid category "{value}". '
            f'Choose one of: {", ".join(PRODUCT_CATEGORIES)}'
        )


class Product(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(
        max_length=100,
        validators=[validate_product_category],
    )
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    def clean(self):
        super().clean()
        if self.price is not None and self.price < Decimal('0'):
            raise ValidationError({'price': 'Price cannot be negative.'})

    def __str__(self):
        return self.title


class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f'{self.user.username} -> {self.product_id}'
