from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('generate/', views.generate_story, name='generate_story'),
    path('storybook/<int:story_id>/', views.view_storybook, name='view_storybook'),
    path('download_pdf/<int:story_id>/', views.download_pdf, name='download_pdf'),
]