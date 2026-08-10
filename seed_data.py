import os
import random
import io
from decimal import Decimal

import django
from PIL import Image

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thrift_store.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from store.models import PRODUCT_CATEGORIES, Product

print("Clearing old data (except superusers if any)...")
Product.objects.all().delete()
User.objects.exclude(username='admin').delete()

print("Generating random images via Python Pillow (AI image server is currently busy)...")
media_dir = os.path.join('media', 'product_images')
os.makedirs(media_dir, exist_ok=True)

def generate_dummy_image(color, text):
    # Generate a beautiful solid color placeholder image
    img = Image.new('RGB', (800, 600), color=color)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return ContentFile(img_byte_arr.getvalue(), name=f'{text}.png')

categories = list(PRODUCT_CATEGORIES)
adjectives = ['Vintage', 'Brand New', 'Used', 'Retro', 'Clean', 'Refurbished', 'Study']
nouns = ['Film Camera', 'Denim Jacket', 'Calculus Textbook', 'Desk Lamp', 'Mechanical Keyboard', 'Monitor', 'Graphic T-Shirt', 'Noise Cancelling Headphones', 'Hiking Backpack']

users = []
print("Creating 20 unique mock users...")
for i in range(20):
    uname = f"student_{i}_{random.randint(100, 999)}"
    u = User.objects.create_user(username=uname, email=f"{uname}@university.edu", password="password123")
    users.append(u)

print("Creating 20 unique items...")
# Beautiful pastel colors for the placeholder images
colors = [
    (255, 183, 178), # Pastel Red/Pink
    (255, 218, 193), # Peach
    (226, 240, 203), # Pastel Green
    (181, 234, 215), # Mint
    (199, 206, 234), # Pastel Purple
]

for user in users:
    title = f"{random.choice(adjectives)} {random.choice(nouns)}"
    desc = f"Selling my {title.lower()}! It's in great condition, I just don't need it for my classes anymore. Pick up near dorms."
    price = Decimal(str(round(random.uniform(5.0, 150.0), 2)))
    cat = random.choice(categories)

    prod = Product(
        user=user,
        title=title,
        description=desc,
        price=price,
        category=cat
    )
    col = random.choice(colors)
    prod.image.save(f"{title.replace(' ', '_').lower()}.png", generate_dummy_image(col, title))
    prod.save()

print("Seed complete! Created 20 users and 20 item posts successfully.")
