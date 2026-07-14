from rest_framework import serializers
from .models import Product, Wishlist

class ProductSerializer(serializers.ModelSerializer):
    seller_username = serializers.CharField(source='user.username', read_only=True)
    seller_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['user']

class WishlistSerializer(serializers.ModelSerializer):
    product_details = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = Wishlist
        fields = '__all__'
