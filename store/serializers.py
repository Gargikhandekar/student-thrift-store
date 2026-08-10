from rest_framework import serializers

from .models import PRODUCT_CATEGORIES, Product, Wishlist


class ProductSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='user.username', read_only=True)
    seller_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['user', 'created_at', 'updated_at']

    def validate_category(self, value):
        value = value.strip() if isinstance(value, str) else value
        if value not in PRODUCT_CATEGORIES:
            raise serializers.ValidationError(
                f'Invalid category. Choose one of: {", ".join(PRODUCT_CATEGORIES)}'
            )
        return value

    def validate_price(self, value):
        if value is None:
            raise serializers.ValidationError('Price is required.')
        if value < 0:
            raise serializers.ValidationError('Price cannot be negative.')
        return value


class WishlistSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = Wishlist
        fields = '__all__'
