import os
import csv
import django
from PIL import Image
import io
import urllib.request
from django.core.files.base import ContentFile
import random

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thrift_store.settings')
django.setup()

from django.contrib.auth.models import User
from store.models import Product

def generate_dummy_image(title):
    color = random.choice([
        (255, 183, 178), (255, 218, 193), (226, 240, 203), (181, 234, 215), (199, 206, 234)
    ])
    img = Image.new('RGB', (800, 600), color=color)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return ContentFile(img_byte_arr.getvalue(), name=f'{title.replace(" ", "_").lower()}.png')

def fetch_image_from_url(url, title):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=10)
        return ContentFile(response.read(), name=f'{title.replace(" ", "_").lower()}.jpg')
    except Exception:
        print(f"Failed to fetch {url}, falling back to placeholder.")
        return generate_dummy_image(title)

csv_file_path = 'products.csv'

if not os.path.exists(csv_file_path):
    print(f"Error: Could not find '{csv_file_path}' in this folder.")
    print("Please create 'products.csv' with columns: title,description,price,category,username,image_url")
    exit()

print("Clearing old products...")
Product.objects.all().delete()

print(f"Reading '{csv_file_path}'...")
with open(csv_file_path, mode='r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    
    count = 0
    for row in reader:
        # Get data from columns
        title = row.get('title', 'Unknown Item').strip()
        description = row.get('description', '').strip()
        price = float(row.get('price', 0.0))
        category = row.get('category', 'Misc').strip()
        username = row.get('username', 'student_demo').strip()
        image_url = row.get('image_url', '').strip()

        # Find or create the user that owns it
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': f"{username}@university.edu"}
        )
        if created:
            user.set_password("password123")
            user.save()

        # Build the product
        prod = Product(
            user=user,
            title=title,
            description=description,
            price=price,
            category=category
        )
        
        # Add real image downloading
        if image_url:
            print(f"Downloading custom image for {title}...")
            prod.image.save(f"{title.replace(' ', '_').lower()}.jpg", fetch_image_from_url(image_url, title))
        else:
            print(f"Generating aesthetic placeholder for {title}...")
            prod.image.save(f"{title.replace(' ', '_').lower()}.png", generate_dummy_image(title))
            
        prod.save()
        count += 1

print(f"Successfully imported {count} items from your dataset!")
