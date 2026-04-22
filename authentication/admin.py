from django.contrib import admin
from django.contrib.auth import get_user_model

# Register the custom User model if you have extended it
User = get_user_model()

admin.site.register(User)