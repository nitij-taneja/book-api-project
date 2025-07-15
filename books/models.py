from django.db import models
from django.core.files.storage import default_storage
import os

class Book(models.Model):
    """
    Model representing a book in the library system.
    This matches the structure shown in the uploaded images.
    """
    
    # Basic book information
    title = models.CharField(max_length=500, verbose_name="العنوان")  # Title/Address column
    author = models.CharField(max_length=300, verbose_name="المؤلف")  # Author column
    description = models.TextField(blank=True, null=True, verbose_name="الوصف")  # Description
    
    # Category information
    category = models.CharField(max_length=200, verbose_name="الفئة")  # Category column
    
    # Status information
    STATUS_CHOICES = [
        ('published', 'منشور'),  # Published
        ('draft', 'مسودة'),      # Draft
        ('pending', 'معلق'),     # Pending
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft',
        verbose_name="الحالة"
    )
    
    # File information
    pdf_file = models.FileField(
        upload_to='books/pdfs/', 
        blank=True, 
        null=True,
        verbose_name="ملف"
    )
    
    # Cover image
    cover_image = models.URLField(
        blank=True, 
        null=True,
        verbose_name="غلاف الكتاب"
    )
    
    # Additional metadata
    isbn = models.CharField(max_length=20, blank=True, null=True)
    publication_date = models.CharField(max_length=20, blank=True, null=True, help_text="Publication date in any format")
    publisher = models.CharField(max_length=200, blank=True, null=True)
    language = models.CharField(max_length=10, default='ar')  # 'ar' for Arabic, 'en' for English
    
    # AI-generated content
    ai_generated_summary = models.TextField(blank=True, null=True)
    related_books = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # View count (as shown in the interface)
    view_count = models.PositiveIntegerField(default=0, verbose_name="عدد المشاهدات")
    
    class Meta:
        verbose_name = "كتاب"
        verbose_name_plural = "الكتب"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.author}"
    
    def get_pdf_url(self):
        """Get the URL for the PDF file if it exists."""
        if self.pdf_file:
            return self.pdf_file.url
        return None
    
    def increment_view_count(self):
        """Increment the view count for this book."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class BookSearchResult(models.Model):
    """
    Temporary model to store search results before user selects which book to add.
    This is used for the AI search functionality.
    """
    
    # Search session identifier
    search_session = models.CharField(max_length=100)
    
    # Book information from external APIs
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=200, blank=True, null=True)
    cover_image_url = models.URLField(blank=True, null=True)
    
    # PDF information
    pdf_url = models.URLField(blank=True, null=True)
    pdf_source = models.CharField(max_length=100, blank=True, null=True)  # e.g., 'gutendx', 'google_books'
    pdf_verified = models.BooleanField(default=False)  # Whether PDF link has been verified
    
    # Additional metadata
    isbn = models.CharField(max_length=20, blank=True, null=True)
    publication_date = models.CharField(max_length=50, blank=True, null=True)
    publisher = models.CharField(max_length=200, blank=True, null=True)
    language = models.CharField(max_length=10, default='en')
    
    # AI-generated content
    ai_summary = models.TextField(blank=True, null=True)
    ai_categories = models.JSONField(default=list, blank=True)
    
    # Source information
    source_api = models.CharField(max_length=50)  # e.g., 'google_books', 'gutendx', 'aco'
    external_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Ranking for search results
    relevance_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-relevance_score', '-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.author} ({self.source_api})"

