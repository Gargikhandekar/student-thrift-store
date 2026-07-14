from django.urls import path
from .views import product_list, delete_product, update_product, api_register, api_login, api_logout, wishlist_view, api_profile

urlpatterns = [
    path('products/', product_list),
    path('delete/<int:id>/', delete_product),
    path('update/<int:id>/', update_product),
    path('register/', api_register),
    path('login/', api_login),
    path('logout/', api_logout),
    path('wishlist/', wishlist_view),
    path('profile/', api_profile),
]
