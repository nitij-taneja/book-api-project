"""
URL patterns for book API endpoints.
"""

from django.urls import path
from . import views

app_name = 'books'

urlpatterns = [
    # Main AI book search endpoint
    path('ai-search/', views.ai_book_search, name='ai_book_search'),

    # AI book search without database operations
    path('ai-search-no-db/', views.ai_book_search_no_db, name='ai_book_search_no_db'),

    # Analyze book description for categories
    path('analyze-description/', views.analyze_book_description, name='analyze_book_description'),

    # Website/Company search endpoint
    path('website-search/', views.website_search, name='website_search'),

    # Author search endpoint
    path('author-search/', views.author_search, name='author_search'),

    # Category information endpoint
    path('category-search/', views.category_search, name='category_search'),

    # Company/Stock search endpoint
    path('company-search/', views.company_search, name='company_search'),

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

