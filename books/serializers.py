"""
Django REST Framework serializers for book models.
"""

from rest_framework import serializers
from .models import Book, BookSearchResult


class BookSerializer(serializers.ModelSerializer):
    """Serializer for Book model."""
    
    pdf_url = serializers.SerializerMethodField()
    cover_image_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Book
        fields = [
            'id',
            'title',
            'author', 
            'description',
            'category',
            'status',
            'status_display',
            'pdf_file',
            'pdf_url',
            'cover_image',
            'cover_image_display',
            'isbn',
            'publication_date',
            'publisher',
            'language',
            'ai_generated_summary',
            'related_books',
            'view_count',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'view_count']
    
    def get_pdf_url(self, obj):
        """Get the full URL for the PDF file."""
        return obj.get_pdf_url()
    
    def get_cover_image_display(self, obj):
        """Get the cover image URL for display."""
        return obj.cover_image if obj.cover_image else None
    
    def get_status_display(self, obj):
        """Get the human-readable status."""
        return obj.get_status_display()


class BookSearchResultSerializer(serializers.ModelSerializer):
    """Serializer for BookSearchResult model."""

    categories_list = serializers.SerializerMethodField()
    ai_categories_list = serializers.SerializerMethodField()
    pdf_verified_status = serializers.SerializerMethodField()
    structured_categories = serializers.SerializerMethodField()
    structured_author = serializers.SerializerMethodField()
    ai_book_summary = serializers.SerializerMethodField()

    class Meta:
        model = BookSearchResult
        fields = [
            'id',
            'search_session',
            'title',
            'author',
            'structured_author',
            'description',
            'category',
            'categories_list',
            'structured_categories',
            'ai_book_summary',
            'cover_image_url',
            'pdf_url',
            'pdf_source',
            'pdf_verified',
            'pdf_verified_status',
            'isbn',
            'publication_date',
            'publisher',
            'language',
            'ai_summary',
            'ai_categories',
            'ai_categories_list',
            'source_api',
            'external_id',
            'relevance_score',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_categories_list(self, obj):
        """Convert category string to list."""
        if obj.category:
            return [cat.strip() for cat in obj.category.split(',') if cat.strip()]
        return []
    
    def get_ai_categories_list(self, obj):
        """Get AI-generated categories as list."""
        if isinstance(obj.ai_categories, list):
            return obj.ai_categories
        return []
    
    def get_pdf_verified_status(self, obj):
        """Get PDF verification status."""
        if not obj.pdf_url:
            return 'no_pdf'
        elif obj.pdf_verified:
            return 'verified'
        else:
            return 'unverified'

    def get_structured_categories(self, obj):
        """Get structured categories with icons and wiki links."""
        # This will be populated from the enhanced results in the view
        return getattr(obj, '_structured_categories', [])

    def get_structured_author(self, obj):
        """Get structured author information."""
        # This will be populated from the enhanced results in the view
        return getattr(obj, '_structured_author', {})

    def get_ai_book_summary(self, obj):
        """Get AI-generated book summary."""
        # This will be populated from the enhanced results in the view
        return getattr(obj, '_ai_book_summary', '')


class BookCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new books."""
    
    class Meta:
        model = Book
        fields = [
            'title',
            'author',
            'description', 
            'category',
            'status',
            'cover_image',
            'isbn',
            'publication_date',
            'publisher',
            'language',
            'ai_generated_summary',
            'related_books'
        ]
    
    def validate_title(self, value):
        """Validate that title is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()
    
    def validate_author(self, value):
        """Validate that author is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Author cannot be empty.")
        return value.strip()


class BookUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing books."""
    
    class Meta:
        model = Book
        fields = [
            'title',
            'author',
            'description',
            'category', 
            'status',
            'cover_image',
            'isbn',
            'publication_date',
            'publisher',
            'language',
            'ai_generated_summary',
            'related_books'
        ]
    
    def validate_title(self, value):
        """Validate that title is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Title cannot be empty.")
        return value.strip()
    
    def validate_author(self, value):
        """Validate that author is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Author cannot be empty.")
        return value.strip()


class SearchSessionSerializer(serializers.Serializer):
    """Serializer for search session data."""
    
    search_session = serializers.CharField(max_length=100)
    total_results = serializers.IntegerField()
    language = serializers.CharField(max_length=10)
    original_query = serializers.CharField(max_length=500)
    extracted_info = serializers.JSONField()
    created_at = serializers.DateTimeField()


class PDFVerificationSerializer(serializers.Serializer):
    """Serializer for PDF verification requests."""
    
    pdf_url = serializers.URLField()
    
    def validate_pdf_url(self, value):
        """Validate PDF URL format."""
        if not value:
            raise serializers.ValidationError("PDF URL is required.")
        return value


class BookAddRequestSerializer(serializers.Serializer):
    """Serializer for book addition requests."""
    
    search_result_id = serializers.IntegerField()
    status = serializers.ChoiceField(
        choices=['draft', 'published', 'pending'],
        default='draft'
    )
    custom_category = serializers.CharField(max_length=200, required=False, allow_blank=True)
    download_pdf = serializers.BooleanField(default=True)
    
    def validate_search_result_id(self, value):
        """Validate that search result exists."""
        try:
            BookSearchResult.objects.get(id=value)
        except BookSearchResult.DoesNotExist:
            raise serializers.ValidationError("Search result not found.")
        return value

