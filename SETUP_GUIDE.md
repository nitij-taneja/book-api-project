# Complete Setup Guide for Book API Project

## Prerequisites

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Git** (for cloning the repository)
- **Groq API Key** (get from https://console.groq.com/)

## Step-by-Step Setup

### 1. Clone the Repository

```bash
git clone https://github.com/nitij-taneja/book-api-project.git
cd book-api-project
```

### 2. Create and Activate Virtual Environment

#### Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### Windows (Command Prompt)
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

#### macOS/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Environment Configuration

#### Option A: Using .env file (Recommended)

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit the `.env` file and add your API keys:
```env
# Required
GROQ_API_KEY=your_actual_groq_api_key_here

# Optional (with defaults)
SECRET_KEY=your-secret-key-here
DEBUG=True
```

#### Option B: Set Environment Variables Directly

**Windows (PowerShell):**
```powershell
$env:GROQ_API_KEY="your_actual_groq_api_key_here"
$env:SECRET_KEY="your-secret-key-here"
$env:DEBUG="True"
```

**Windows (Command Prompt):**
```cmd
set GROQ_API_KEY=your_actual_groq_api_key_here
set SECRET_KEY=your-secret-key-here
set DEBUG=True
```

**macOS/Linux:**
```bash
export GROQ_API_KEY="your_actual_groq_api_key_here"
export SECRET_KEY="your-secret-key-here"
export DEBUG="True"
```

### 5. Database Setup(not needed already done only if any chnage in models.py )

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 7. Run the Development Server

```bash
python manage.py runserver
```

The API will be available at: `http://localhost:8000`

## Getting Your Groq API Key

1. Visit https://console.groq.com/
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key and use it in your environment configuration

## Troubleshooting

### Common Issues

1. **"GROQ_API_KEY environment variable is required" error**
   - Make sure you've set the GROQ_API_KEY environment variable
   - If using .env file, ensure it's in the project root directory
   - Restart your terminal/IDE after setting environment variables

2. **Module not found errors**
   - Ensure your virtual environment is activated
   - Run `pip install -r requirements.txt` again

3. **Database errors**
   - Run `python manage.py makemigrations` and `python manage.py migrate`
   - Delete `db.sqlite3` and run migrations again if needed

4. **Port already in use**
   - Use a different port: `python manage.py runserver 8001`
   - Or kill the process using port 8000

### Verification Steps

1. **Check if server is running:**
   ```bash
   curl http://localhost:8000/api/books/
   ```

2. **Test AI search endpoint:**
   ```bash
   curl -X POST http://localhost:8000/api/books/ai-search/ \
     -H "Content-Type: application/json" \
     -d '{"book_name": "Pride and Prejudice", "language": "en", "max_results": 3}'
   ```

## Production Deployment

For production deployment:

1. Set `DEBUG=False` in your environment
2. Configure a proper SECRET_KEY
3. Use a production database (PostgreSQL recommended)
4. Use a WSGI server like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn book_api_project.wsgi:application
   ```

## Security Notes

- Never commit your `.env` file or API keys to version control
- Use strong SECRET_KEY in production
- Set DEBUG=False in production
- Configure proper ALLOWED_HOSTS for production
