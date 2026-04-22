from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    # Registration & Login
    path('register/', views.RegisterUser.as_view(), name='register'),
    path('login/', views.LoginUser.as_view(), name='login'),
    path('logout/', views.LogoutUser.as_view(), name='logout'),

    # Silent auto-refresh — Frontend calls this automatically when access token expires
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Profile & Password Management
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),

    # Forgot Password Flow (2 steps)
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot_password'),           # Step 1 — send email
    path('reset-password/confirm/', views.ResetPasswordConfirmView.as_view(), name='reset_password_confirm'),  # Step 2 — set new password

    # MFA Setup
    path('mfa/enable/', views.EnableMFAView.as_view(), name='mfa_enable'),
    path('mfa/verify/', views.VerifyMFAView.as_view(), name='mfa_verify'),
]