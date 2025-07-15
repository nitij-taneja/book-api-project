"""
URL patterns for book API endpoints.
"""

from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    # Main AI book search endpoint
    path('ai-search/', views.ai_book_search, name='ai_book_search'),
    
    # Add book from search results
    path('add-from-search/', views.add_book_from_search, name='add_book_from_search'),
    
    # Get search results for a session
    path('search-results/<str:search_session>/', views.get_search_results, name='get_search_results'),
    
    # Verify PDF link
    path('verify-pdf/', views.verify_pdf_link, name='verify_pdf_link'),
    
    # List and manage books
    path('', views.list_books, name='list_books'),
    path('<int:book_id>/', views.get_book_details, name='get_book_details'),
]

