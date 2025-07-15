# AI-Powered Book Search API

A Django REST API that uses AI (Groq LLM) to search for books and find verified PDF download links from multiple sources including Google Books, Project Gutenberg, Internet Archive, and Arabic Collections Online.

## Features

- 🤖 AI-powered book search using Groq LLM
- 📚 Multi-source book search (Google Books, Gutenberg, Internet Archive, ACO)
- ✅ PDF link verification before returning results
- 🔍 Intelligent PDF discovery from reliable sources
- 🌐 Support for both English and Arabic books
- 📊 Relevance scoring and result ranking
- 🎯 Returns only top 5 verified results

## Prerequisites

- Python 3.8 or higher
- Groq API key (get from https://console.groq.com/)

## Installation & Setup

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd book_api_project
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
**IMPORTANT:** You must set up your Groq API key as an environment variable.

#### Option 1: Create a `.env` file (Recommended)
Create a `.env` file in the project root:
```env
GROQ_API_KEY=your_groq_api_key_here
DEBUG=True
SECRET_KEY=your-secret-key-here
```

#### Option 2: Set Environment Variables Directly
```bash
# Windows (PowerShell)
$env:GROQ_API_KEY="your_groq_api_key_here"

# Windows (Command Prompt)
set GROQ_API_KEY=your_groq_api_key_here

# macOS/Linux
export GROQ_API_KEY="your_groq_api_key_here"
```

**Note:** The application will not start without a valid GROQ_API_KEY environment variable.

### 5. Database Setup ( already done no need to do it unless any chnage in models.py )
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Optional)
```bash
python manage.py createsuperuser
```

## Running the Server

### Development Server
```bash
python manage.py runserver
```

The API will be available at: `http://localhost:8000`

### Production Server
For production, use a WSGI server like Gunicorn:
```bash
pip install gunicorn
gunicorn book_api_project.wsgi:application
```

## API Documentation

### Base URL
```
http://localhost:8000/api/books/
```

### Endpoints

#### 1. AI Book Search
**POST** `/api/books/ai-search/`

Search for books using AI-powered query understanding and return verified PDF links.

**Request Body:**
```json
{
    "book_name": "Pride and Prejudice",
    "language": "en",
    "max_results": 5
}
```

**Parameters:**
- `book_name` (string, required): The book title or search query
- `language` (string, optional): Language preference ("en" or "ar", default: "en")
- `max_results` (integer, optional): Maximum number of results (default: 5)

**Response:**
```json
{
    "search_session": "uuid-string",
    "results": [
        {
            "id": 1,
            "title": "Pride and Prejudice",
            "author": "Jane Austen",
            "description": "A classic novel...",
            "category": "Fiction, Romance",
            "cover_image_url": "https://example.com/cover.jpg",
            "pdf_url": "https://archive.org/download/book.pdf",
            "pdf_source": "known_source",
            "pdf_verified": true,
            "pdf_verified_status": "verified",
            "isbn": "978-0-123456-78-9",
            "publication_date": "1813",
            "publisher": "Publisher Name",
            "language": "en",
            "source_api": "google_books",
            "relevance_score": 1.3,
            "created_at": "2024-01-01T12:00:00Z"
        }
    ],
    "total_found": 1,
    "extracted_info": {
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "categories": ["Fiction", "Romance"],
        "language": "en"
    }
}
```

#### 2. Add Book from Search Results
**POST** `/api/books/add-from-search/`

Add a selected book from search results to the main database.

**Request Body:**
```json
{
    "search_result_id": 1,
    "status": "published",
    "custom_category": "Classic Literature",
    "download_pdf": true
}
```

#### 3. Get Search Results
**GET** `/api/books/search-results/{search_session}/`

Retrieve search results for a specific search session.

#### 4. Verify PDF Link
**POST** `/api/books/verify-pdf/`

Verify if a PDF link is accessible.

**Request Body:**
```json
{
    "pdf_url": "https://example.com/book.pdf"
}
```

#### 5. List Books
**GET** `/api/books/`

Get all books in the database.

#### 6. Get Book Details
**GET** `/api/books/{book_id}/`

Get details of a specific book.

## Testing

### Run Tests
```bash
python manage.py test
```

### Test API Endpoints
Use the provided test scripts:

```bash
# Test PDF enhancement functionality
python test_verified_pdf_search.py

# Test API endpoint
python test_api_endpoint.py
```

### Manual Testing with cURL

```bash
# Search for books
curl -X POST http://localhost:8000/api/books/ai-search/ \
  -H "Content-Type: application/json" \
  -d '{
    "book_name": "The Great Gatsby",
    "language": "en",
    "max_results": 3
  }'
```

## Configuration

### Groq API Settings
Update in `book_api_project/settings.py`:
```python
GROQ_API_KEY = 'your_api_key_here'
```

### File Upload Settings
```python
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
```

### CORS Settings
```python
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
```

## Troubleshooting

### Common Issues

1. **Groq API Key Error**
   - Ensure your Groq API key is valid and properly set
   - Check API rate limits

2. **PDF Verification Timeouts**
   - Some PDF links may timeout during verification
   - The system will try multiple sources automatically

3. **Network Issues**
   - Ensure internet connection for external API calls
   - Some sources (like gutendx.com) may be temporarily unavailable

### Debug Mode
Enable debug logging by setting `DEBUG = True` in settings.py

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License.
