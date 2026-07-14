from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Product
from .serializers import ProductSerializer


# ------------------ FRONTEND ------------------

# Home page
def home(request):
    return render(request, 'index.html')


# ------------------ API AUTH ------------------
from django.contrib.auth import authenticate, login, logout

@api_view(['POST'])
def api_register(request):
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)

    user = User.objects.create_user(username=username, email=email, password=password)
    login(request, user)
    return Response({'message': 'Registered and logged in', 'username': username})

@api_view(['POST'])
def api_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(request, username=username, password=password)
    
    if user is not None:
        login(request, user)
        return Response({
            'message': 'Logged in', 
            'username': username, 
            'is_superuser': user.is_superuser
        })
    return Response({'error': 'Invalid credentials'}, status=400)

@api_view(['POST'])
def api_logout(request):
    logout(request)
    return Response({'message': 'Logged out'})

@api_view(['GET'])
def api_profile(request):
    if request.user.is_authenticated:
        return Response({
            'username': request.user.username,
            'is_superuser': request.user.is_superuser
        })
    return Response({'error': 'Not logged in'}, status=403)



from django.db.models import Q

# GET + POST (products)
@api_view(['GET', 'POST'])
def product_list(request):

    # GET (view + search + filter)
    if request.method == 'GET':
        query = request.GET.get('search', '').strip()
        category = request.GET.get('category', '').strip()
        min_price = request.GET.get('min_price', '').strip()
        max_price = request.GET.get('max_price', '').strip()

        products = Product.objects.all()

        if query:
            # Check every word in the search box independently!
            for word in query.split():
                products = products.filter(
                    Q(title__icontains=word) | 
                    Q(description__icontains=word) |
                    Q(category__icontains=word)
                )
                
        if category:
            products = products.filter(category__icontains=category)
        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)

        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


    # POST (add product)
    if request.method == 'POST':

        if not request.user.is_authenticated:
            return Response({"error": "Login required"}, status=403)

        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data)

        return Response(serializer.errors)


# DELETE product
@api_view(['DELETE'])
def delete_product(request, id):

    product = Product.objects.get(id=id)

    # Only owner or admin can delete
    if product.user != request.user and not request.user.is_superuser:
        return Response({"error": "Not allowed"}, status=403)

    product.delete()
    return Response({"message": "Deleted"})


# UPDATE product
@api_view(['PUT'])
def update_product(request, id):

    product = Product.objects.get(id=id)

    # Only owner or admin can update
    if product.user != request.user and not request.user.is_superuser:
        return Response({"error": "Not allowed"}, status=403)

    serializer = ProductSerializer(product, data=request.data)

    if serializer.is_valid():
        serializer.save(user=request.user)
        return Response(serializer.data)

    return Response(serializer.errors)


# ------------------ WISHLIST API ------------------
from .models import Wishlist
from .serializers import WishlistSerializer

@api_view(['GET', 'POST'])
def wishlist_view(request):
    if not request.user.is_authenticated:
        return Response({"error": "Login required"}, status=403)

    if request.method == 'GET':
        wishlist = Wishlist.objects.filter(user=request.user)
        serializer = WishlistSerializer(wishlist, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        product_id = request.data.get('product_id')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found"}, status=404)

        wishlist_item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        if not created:
            wishlist_item.delete()
            return Response({"message": "Removed from wishlist", "status": "removed"})

        serializer = WishlistSerializer(wishlist_item)
        return Response({"message": "Added to wishlist", "item": serializer.data, "status": "added"})